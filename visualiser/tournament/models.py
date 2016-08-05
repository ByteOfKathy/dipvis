# Diplomacy Tournament Visualiser
# Copyright (C) 2014 Chris Brand
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django.db import models
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db.models import Max, Min, Sum, Q

from tournament.background import *

import urllib2, random

SPRING = 'S'
FALL = 'F'
SEASONS = (
    (SPRING, 'spring'),
    (FALL, 'fall'),
)
MOVEMENT = 'M'
RETREATS = 'R'
# Use X for adjustments to simplify sorting
ADJUSTMENTS = 'X'
PHASES = (
    (MOVEMENT, 'movement'),
    (RETREATS, 'retreats'),
    (ADJUSTMENTS, 'adjustments'),
)
phase_str = {
    MOVEMENT: 'M',
    RETREATS: 'R',
    ADJUSTMENTS: 'A',
}

FIRST_YEAR = 1901

TOTAL_SCS = 34
WINNING_SCS = ((TOTAL_SCS/2)+1)

# These happen to co-incide with the coding used by the WDD
GAME_RESULT = (
    ('W', 'Win'),
    ('D2', '2-way draw'),
    ('D3', '3-way draw'),
    ('D4', '4-way draw'),
    ('D5', '5-way draw'),
    ('D6', '6-way draw'),
    ('D7', '7-way draw'),
    ('L', 'Loss'),
)

# Default initial position image
S1901M_IMAGE = u's1901m.gif'

# Power assignment methods
RANDOM = 'R'
FRENCH_METHOD = 'F'
POWER_ASSIGNS =  (
    (RANDOM, 'Random'),
    (FRENCH_METHOD, 'French method'),
)

# Mask values to choose which background strings to include
MASK_TITLES = 1<<0
MASK_TOURNEY_COUNT = 1<<1
MASK_FIRST_TOURNEY = 1<<2
MASK_LAST_TOURNEY = 1<<3
MASK_BEST_TOURNEY_RESULT = 1<<4
MASK_GAMES_PLAYED = 1<<5
MASK_BEST_SC_COUNT = 1<<6
MASK_SOLO_COUNT = 1<<7
MASK_ELIM_COUNT = 1<<8
MASK_BOARD_TOP_COUNT = 1<<9
MASK_ROUND_ENDPOINTS = 1<<10
MASK_ALL_BG = (1<<11)-1

# Mask values to choose which news strings to include
MASK_BOARD_TOP = 1<<0
MASK_GAINERS = 1<<1
MASK_LOSERS = 1<<2
MASK_DRAW_VOTES = 1<<3
MASK_ELIMINATIONS = 1<<4
MASK_ALL_NEWS = (1<<5)-1

TITLE_MAP = {
    'World Champion' : 1,
    'North American Champion' : 1,
    'Winner' : 1,
    'European Champion' : 1,
    'Second' : 2,
    'Third' : 3,
}

class GameScoringSystem():
    # TODO This doesn't deal with multiple players playing one power
    """
    A scoring system for a Game.
    Provides a method to calculate a score for each player of one game.
    """
    name = u''
    # True for classes that provide building blocks rather than full scoring systems
    is_abstract = True

    def _the_game(self, centre_counts):
        """Returns the game in question."""
        return centre_counts[0].game

    def _final_year(self, centre_counts):
        """Returns the most recent year we have centre counts for."""
        return centre_counts.order_by('-year')[0].year

    def _final_year_scs(self, centre_counts):
        """Returns the CentreCounts for the most recent year only, ordered largest-to-smallest."""
        return centre_counts.filter(year=self._final_year(centre_counts)).order_by('-count')

    def _survivor_count(self, centre_counts):
        """Returns the number of surviving powers"""
        return self.final_year_scs(centre_counts).filter(count__gt=0).count()

    def scores(self, centre_counts):
        """
        Takes the set of CentreCount objects for one Game.
        Returns a dict, indexed by power id, of scores.
        """
        return {}

class GScoringSolos(GameScoringSystem):
    """
    Solos score 100 points.
    Other results score 0.
    """
    def __init__(self):
        self.is_abstract = False
        self.name = u'Solo or bust'

    def scores(self, centre_counts):
        """
        If any power soloed, they get 100 points.
        Otherwise, they get 0.
        Return a dict, indexed by power id, of scores.
        """
        retval = {}
        # We only care about the most recent centrecounts
        for sc in self._final_year_scs(centre_counts):
            retval[sc.power] = 0
            if sc.count >= WINNING_SCS:
                retval[sc.power] = 100.0
        return retval

class GScoringDrawSize(GameScoringSystem):
    """
    Solos score 100 points.
    Draw sharers split 100 points between them.
    """
    def __init__(self):
        self.is_abstract = False
        self.name = u'Draw size'

    def scores(self, centre_counts):
        """
        If any power soloed, they get 100 points.
        Otherwise, if a draw passed, all powers in the draw equally shared 100 points between them.
        Otherwise, all surviving powers equally share 100 points between them.
        Return a dict, indexed by power id, of scores.
        """
        retval = {}
        the_game = self._the_game(centre_counts)
        is_dias = the_game.is_dias()
        draw = the_game.passed_draw()
        survivors = self._survivor_count(centre_counts)
        # We only care about the most recent centrecounts
        for sc in self._final_year_scs(centre_counts):
            retval[sc.power] = 0
            if sc.count >= WINNING_SCS:
                retval[sc.power] = 100.0
            elif draw and sc.power in draw.powers():
                retval[sc.power] = 100.0 / draw.draw_size()
            elif sc.count > 0:
                retval[sc.power] = 100.0 / survivors
        return retval

def adjust_rank_score(centre_counts, rank_points):
    """
    Takes a list of CentreCounts for one year of one game, ordered highest-to-lowest
    and a list of ranking points for positions, ordered from first place to last.
    Returns a list of ranking points for positions, ordered to correspond to the centre counts,
    having made adjustments for any tied positions.
    Where two or more powers have the same score, the ranking points for their positions
    are shared eveny between them.
    """
    # Nothing to do if there are no rank points to share out
    if len(rank_points) == 0:
        return []
    # First count up how many powers tied at the top
    i = 0
    count = 0
    points = 0
    scs = centre_counts[0].count
    while (i < len(centre_counts)) and (centre_counts[i].count == scs):
        count += 1
        if i < len(rank_points):
            points += rank_points[i]
        i += 1
    # Now share the points between those tied players
    for j in range(0,i):
        if j < len(rank_points):
            rank_points[j] = points / count
        else:
            rank_points.append(points / count)
    # And recursively continue
    return rank_points[0:i] + adjust_rank_score(centre_counts[i:], rank_points[i:])

class GScoringCDiplo(GameScoringSystem):
    """
    If there is a solo:
    - Soloers score a set number of points (soloer_pts).
    - Losers to a solo may optionally also score some set number of points (loss_pts).
    Otherwise:
    - Participants get some points (played_pts).
    - Everyone gets one point per centre owned.
    - Power with the most centres gets a set number of points (first_pts).
    - Power with the second most centres gets a set number of points (second_pts).
    - Power with the third most centres gets a set number of points (third_pts).
    - if powers are tied for rank, they split the points for their ranks.
    """
    def __init__(self, name, soloer_pts, played_pts, first_pts, second_pts, third_pts, loss_pts=0):
        self.is_abstract = False
        self.name = name
        self.soloer_pts = soloer_pts
        self.played_pts = played_pts
        self.position_pts = [first_pts, second_pts, third_pts]
        self.loss_pts = loss_pts

    def scores(self, centre_counts):
        retval = {}
        final_scs = self._final_year_scs(centre_counts)
        # Tweak the ranking points to allow for ties
        rank_pts = adjust_rank_score(centre_counts, self.position_pts)
        i = 0
        for sc in final_scs:
            if final_scs[0].count >= WINNING_SCS:
                retval[sc.power] = self.loss_pts
                if sc.count >= WINNING_SCS:
                    retval[sc.power] = self.soloer_pts
            else:
                retval[sc.power] = self.played_pts + sc.count + rank_pts[i]
            i += 1
        return retval

class GScoringSumOfSquares(GameScoringSystem):
    """
    Soloer gets 100 points, everyone else gets zero.
    If there is no solo, square each power's final centre-count and normalize those numbers to
    sum to 100 points.
    """
    def __init__(self):
        self.name = "Sum of Squares"
        self.is_abstract = False

    def scores(self, centre_counts):
        retval = {}
        retval_solo = {}
        solo_found = False
        final_scs = self._final_year_scs(centre_counts)
        sum_of_squares = 0
        for sc in final_scs:
            retval_solo = 0
            retval[sc.power] = sc.count * sc.count * 1.0
            sum_of_squares += sc.count
            if sc.count >= WINNING_SCS:
                # Overwrite the previous totals we came up with
                retval_solo[sc.power] = 100.0
                solo_found = True
        if solo_found:
            return retval_solo
        for sc in final_scs:
            retval[sc.power] /= sum_of_squares
        return retval

# All the game scoring systems we support
G_SCORING_SYSTEMS = [
    GScoringSolos(),
    GScoringDrawSize(),
    GScoringCDiplo("CDiplo 100", 100.0, 1.0, 38.0, 14.0, 7.0),
    GScoringCDiplo("CDiplo 80", 80.0, 0.0, 25.0, 14.0, 7.0),
    GScoringSumOfSquares(),
]

class RoundScoringSystem():
    """
    A scoring system for a Round.
    Provides a method to calculate a score for each player of one round.
    """
    name = u''
    # True for classes that provide building blocks rather than full scoring systems
    is_abstract = True

    def scores(self, game_players):
        """
        Takes the set of GamePlayer objects of interest.
        Returns a dict, indexed by player key, of scores.
        """
        return {}

class RScoringBest(RoundScoringSystem):
    """
    Take the best of any game scores for that round.
    """
    def __init__(self):
        self.is_abstract = False
        self.name = u'Best game counts'

    def scores(self, game_players):
        """
        If any player played multiple games, take the best game score.
        Otherwise, just take their game score.
        Return a dict, indexed by player key, of scores.
        """
        retval = {}
        # for each player who played any of the specified games
        for p in Player.objects.filter(gameplayer_set__in=game_players):
            # Find just their games, in order of decreasing score
            player_games = game_players.filter(player=p).order_by('-score')
            # Take the score from the first in the list
            retval[p.player] = player_games[:1].score
        return retval

# All the round scoring systems we support
R_SCORING_SYSTEMS = [
    RScoringBest(),
]

class TournamentScoringSystem():
    """
    A scoring system for a Tournament.
    Provides a method to calculate a score for each player of tournament.
    """
    name = u''
    # True for classes that provide building blocks rather than full scoring systems
    is_abstract = True

    def scores(self, round_players):
        """
        Takes the set of RoundPlayer objects of interest.
        Combines the score attribute of ones for each player into an overall score for that player.
        Returns a dict, indexed by player key, of scores.
        """
        return {}

class TScoringSum(TournamentScoringSystem):
    """
    Just add up the best N round scores.
    """
    scored_rounds = 0

    def __init__(self, name, scored_rounds):
        self.is_abstract = False
        self.name = name
        self.scored_rounds = scored_rounds

    def scores(self, round_players):
        """
        If a player played more than N rounds, sum the best N round scores.
        Otherwise, sum all their round scores.
        Return a dict, indexed by player key, of scores.
        """
        retval = {}
        # for each player who played any of the specified rounds
        for p in Player.objects.filter(roundplayer_set__in=round_players):
            score = 0
            # Find just their rounds, in order of decreasing score
            player_rounds = round_players.filter(player=p).order_by('-score')
            # Add up the first N
            for pr in player_rounds[:self.scored_rounds]:
                score += pr.score
            retval[p.player] = score
        return retval

# All the tournament scoring systems we support
T_SCORING_SYSTEMS = [
    TScoringSum("Sum best 2 rounds", 2),
    TScoringSum("Sum best 3 rounds", 3),
    TScoringSum("Sum best 4 rounds", 4),
]

def get_scoring_systems(systems):
    return sorted([(s.name, s.name) for s in systems if not s.is_abstract])

def validate_year(value):
    """
    Checks for a valid game year
    """
    if value < FIRST_YEAR:
        raise ValidationError(u'%s is not a valid game year' % value)

def validate_year_including_start(value):
    """
    Checks for a valid game year, allowing 1900, too
    """
    if value < FIRST_YEAR-1:
        raise ValidationError(u'%s is not a valid game year' % value)

def validate_sc_count(value):
    """
    Checks for a valid SC count
    """
    if value < 0 or value > TOTAL_SCS:
        raise ValidationError(u'%s is not a valid SC count' % value)

# TODO Not used
def validate_wdd_id(value):
    """
    Checks a WDD id
    """
    url = u'http://world-diplomacy-database.com/php/results/player_fiche.php?id_player=%d' % value
    p = urllib2.urlopen(url)
    if p.geturl() != url:
        raise ValidationError(u'%d is not a valid WDD Id' % value)

class GreatPower(models.Model):
    """
    One of the seven great powers that can be played
    """
    name = models.CharField(max_length=20, unique=True)
    abbreviation = models.CharField(max_length=1, unique=True)
    colour = models.CharField(max_length=20)
    starting_centres = models.PositiveIntegerField()
    class Meta:
        ordering = ['name']
    def __unicode__(self):
        return self.name

def add_player_bg(player):
    """
    Cache background data for the player
    """
    wdd = player.wdd_player_id
    if wdd:
        try:
            bg = Background(wdd)
        except WDDNotAccessible:
            return
        # Titles won
        titles = bg.titles()
        for title in titles:
            pos = None
            the_title = None
            for key,val in TITLE_MAP.iteritems():
                try:
                    if title[key] == unicode(player):
                        pos = val
                        if key.find('Champion') != -1:
                            the_title = key
                except KeyError:
                    pass
            if pos:
                i, created = PlayerRanking.objects.get_or_create(player=player,
                                                                 tournament=title['Tournament'],
                                                                 position=pos,
                                                                 year=title['Year'])
                if the_title:
                    i.title = the_title
                i.save()
        # Podium finishes
        finishes = bg.finishes()
        for finish in finishes:
            d = finish['Date']
            i,created = PlayerRanking.objects.get_or_create(player=player,
                                                            tournament=finish['Tournament'],
                                                            position=finish['Position'],
                                                            year=d[:4])
            i.date = d
            i.save()
        # Tournaments
        tournaments = bg.tournaments()
        for t in tournaments:
            d = t['Date']
            try:
                i,created = PlayerRanking.objects.get_or_create(player=player,
                                                                tournament=t['Name of the tournament'],
                                                                position=t['Rank'],
                                                                year=d[:4])
                i.date = d
                i.save()
            except KeyError:
                # No rank implies they were the TD or similar - just ignore that tournament
                print("Ignoring %s for %s" % (t['Name of the tournament'], player))
                pass
        # Boards
        boards = bg.boards()
        for b in boards:
            try:
                power = b['Country']
                p=GreatPower.objects.get(name__contains=power)
            except GreatPower.DoesNotExist:
                # Apparently not a Standard game
                continue
            i,created = PlayerGameResult.objects.get_or_create(tournament_name=b['Name of the tournament'],
                                                               game_name=b['Round / Board'],
                                                               player=player,
                                                               power=p,
                                                               date = b['Date'],
                                                               position = b['Position'])
            # If there's no 'Position sharing', they were alone at that position
            try:
                i.position_equals = b['Position sharing']
            except KeyError:
                i.position_equals = 1
            # Ignore any of these that aren't present
            try:
                i.score = b['Score']
            except KeyError:
                pass
            try:
                i.final_sc_count = b['Final SCs']
            except KeyError:
                pass
            try:
                i.result = b['Game end']
            except KeyError:
                pass
            try:
                i.year_eliminated = b['Elimination year']
            except KeyError:
                pass
            i.save()

def position_str(position):
    """
    Returns the string version of the position e.g. '1st', '12th'.
    """
    result = unicode(position)
    pos = position % 100
    if pos > 3 and pos < 21:
        result += u'th'
    elif pos % 10 == 1:
        result += u'st'
    elif pos % 10 == 2:
        result += u'nd'
    elif pos % 10 == 3:
        result += u'rd'
    else:
        result += u'th'
    return result

class Player(models.Model):
    """
    A person who played Diplomacy
    """
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    wdd_player_id = models.PositiveIntegerField(unique=True, verbose_name='WDD player id', blank=True, null=True)
    # TODO Would be nice to support a picture of the player, too

    class Meta:
        ordering = ['last_name', 'first_name']

    def __unicode__(self):
        return u'%s %s' % (self.first_name, self.last_name)

    def save(self, *args, **kwargs):
        super(Player, self).save(*args, **kwargs)
        add_player_bg(self)

    def clean(self):
        if not self.wdd_player_id:
            return
        # Check that the WDD id seems to match the name
        try:
            bg = Background(self.wdd_player_id)
        except WDDNotAccessible:
            # Not much we can do in this case
            return
        except InvalidWDDId:
            raise ValidationError, u'WDD Id %d is invalid' % self.wdd_player_id
        # TODO This may be too strict
        wdd_name = bg.name()
        if wdd_name != self.__unicode__():
            raise ValidationError, u'WDD Id %d is for %s, not %s %s' % (self.wdd_player_id, wdd_name, self.first_name, self.last_name)

    def _rankings(self, mask=MASK_ALL_BG):
        """ List of titles won and tournament rankings"""
        results = []
        ranking_set = self.playerranking_set.order_by('year')
        plays = ranking_set.count()
        if plays == 0:
            return results
        if (mask & MASK_TOURNEY_COUNT) != 0:
            results.append(u'%s has competed in %d tournament(s).' % (self, plays))
        if (mask & MASK_TITLES) != 0:
            # Add summaries of actual titles
            titles = {}
            for ranking in ranking_set:
                if ranking.title:
                    if ranking.title not in titles:
                        titles[ranking.title] = []
                    titles[ranking.title].append(ranking.year)
            for key, lst in titles.iteritems():
                results.append(str(self) + ' was ' + key + ' in ' + ', '.join(map(str, lst)) + '.')
        if (mask & MASK_FIRST_TOURNEY) != 0:
            first = ranking_set.first()
            results.append(u'%s first competed in a tournament (%s) in %d.' % (self, first.tournament, first.year))
        if (mask & MASK_LAST_TOURNEY) != 0:
            last = ranking_set.last()
            results.append(u'%s most recently competed in a tournament (%s) in %d.' % (self, last.tournament, last.year))
        if (mask & MASK_BEST_TOURNEY_RESULT) != 0:
            wins = ranking_set.filter(position=1).count()
            if wins > 1:
                results.append(u'%s has won %d tournaments.' % (self, wins))
            elif wins > 0:
                results.append(u'%s has won %d tournament.' % (self, wins))
            else:
                best = ranking_set.aggregate(Min('position'))['position__min']
                pos = position_str(best)
                results.append(u'The best tournament result for %s is %s.' % (self, pos))
        return results

    def _results(self, power=None, mask=MASK_ALL_BG):
        """ List of tournament game achievements, optionally with one Great Power """
        results = []
        results_set = self.playergameresult_set.order_by('year')
        if power:
            results_set = results_set.filter(power=power)
            c_str = u' as %s' % power
        else:
            c_str = ''
        games = results_set.count()
        if games == 0:
            if (mask & MASK_GAMES_PLAYED) != 0:
                results.append(u'%s has never played%s in a tournament before.' % (self, c_str))
            return results
        if (mask & MASK_GAMES_PLAYED) != 0:
            results.append(u'%s has played %d tournament games%s.' % (self, games, c_str))
        if (mask & MASK_BEST_SC_COUNT) != 0:
            best = results_set.aggregate(Max('final_sc_count'))['final_sc_count__max']
            results.append(u'%s has finished with as many as %d centres%s in tournament games.' % (self, best, c_str))
            solo_set = results_set.filter(final_sc_count__gte=WINNING_SCS)
        if (mask & MASK_SOLO_COUNT) != 0:
            solos = solo_set.count()
            if solos > 0:
                results.append(u'%s has soloed %d of %d tournament games played%s (%.2f%%).' % (self, solos, games, c_str, 100.0*float(solos)/float(games)))
            else:
                results.append(u'%s has yet to solo%s at a tournament.' % (self, c_str))
        if (mask & MASK_ELIM_COUNT) != 0:
            query = Q(year_eliminated__isnull=False) | Q(final_sc_count=0)
            eliminations_set = results_set.filter(query)
            eliminations = eliminations_set.count()
            if eliminations > 0:
                results.append(u'%s was eliminated in %d of %d tournament games played%s (%.2f%%).' % (self, eliminations, games, c_str, 100.0*float(eliminations)/float(games)))
            else:
                results.append(u'%s has yet to be eliminated%s in a tournament.' % (self, c_str))
        if (mask & MASK_BOARD_TOP_COUNT) != 0:
            query = Q(result='W') | Q(position=1)
            victories_set = results_set.filter(query)
            board_tops = victories_set.count()
            if board_tops > 0:
                results.append(u'%s topped the board in %d of %d tournament games played%s (%.2f%%).' % (self, board_tops, games, c_str, 100.0*float(board_tops)/float(games)))
            else:
                results.append(u'%s has yet to top the board%s at a tournament.' % (self, c_str))
        return results

    def background(self, power=None, mask=MASK_ALL_BG):
        """
        List of background strings about the player, optionally as a specific Great Power
        """
        if not power:
            return self._rankings(mask=mask) + self._results(mask=mask)
        return self._results(power, mask=mask)

class Tournament(models.Model):
    """
    A Diplomacy tournament
    """
    name = models.CharField(max_length=20)
    start_date = models.DateField()
    end_date = models.DateField()
    # How do we combine round scores to get an overall player tournament score ?
    # This is the name of a TournamentScoringSystem object
    tournament_scoring_system = models.CharField(max_length=40,
                                                 choices=get_scoring_systems(T_SCORING_SYSTEMS),
                                                 help_text='How to combine round scores into a tournament score')
    # How do we combine game scores to get an overall player score for a round ?
    # This is the name of a RoundScoringSystem object
    round_scoring_system = models.CharField(max_length=40,
                                            choices=get_scoring_systems(R_SCORING_SYSTEMS),
                                            help_text='How to combine game scores into a round score')

    class Meta:
        ordering = ['-start_date']

    def background(self, mask=MASK_ALL_BG):
        """
        Returns a list of background strings for the tournament
        """
        players = Player.objects.filter(tournamentplayer__tournament = self)
        results = []
        for p in players:
            results += p.background(mask=mask)
        # Shuffle the resulting list
        random.shuffle(results)
        return results

    def news(self):
        """
        Returns a list of news strings for the tournament
        """
        results = []
        # TODO This should probably just call through to the current round's news() method
        current_round = self.current_round()
        if current_round:
            for g in current_round.game_set.all():
                results += g.news(include_game_name=True)
        else:
            # TODO list top few scores in previous round, perhaps ?
            pass
        # Shuffle the resulting list
        random.shuffle(results)
        return results

    def current_round(self):
        """
        Returns the Round in progress, or None
        """
        # Rely on the default ordering
        rds = self.round_set.all()
        for r in rds:
            if not r.is_finished():
                return r
        return None

    def is_finished(self):
        for r in self.round_set.all():
            if not r.is_finished():
                return False
        return True

    def get_absolute_url(self):
        return reverse('tournament_detail', args=[str(self.id)])

    def __unicode__(self):
        return self.name

class TournamentPlayer(models.Model):
    """
    One player in a tournament
    """
    player = models.ForeignKey(Player)
    tournament = models.ForeignKey(Tournament)
    score = models.FloatField(default=0.0)

    class Meta:
        ordering = ['player']

    def __unicode__(self):
        return u'%s %s %f' % (self.tournament, self.player, self.score)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super(TournamentPlayer, self).save(*args, **kwargs)
        # Update background info when a player is added to the Tournament (only)
        if is_new:
            add_player_bg(self.player)

class Round(models.Model):
    """
    A single round of a Tournament
    """
    tournament = models.ForeignKey(Tournament)
    number = models.PositiveSmallIntegerField()
    # How do we combine game scores to get an overall player score for a round ?
    # This is the name of a GameScoringSystem object
    # There has at least been talk of tournaments using multiple scoring systems, one per round
    scoring_system = models.CharField(max_length=40,
                                      verbose_name='Game scoring system',
                                      choices=get_scoring_systems(G_SCORING_SYSTEMS),
                                      help_text='How to calculate a score for one game')
    dias = models.BooleanField(verbose_name='Draws Include All Survivors')
    final_year = models.PositiveSmallIntegerField(blank=True, null=True, validators=[validate_year])
    earliest_end_time = models.DateTimeField(blank=True, null=True)
    latest_end_time = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['number']

    def is_finished(self):
        gs = self.game_set.all()
        if len(gs) == 0:
            # Rounds with no games can't have started
            return False
        for g in gs:
            if not g.is_finished:
                return False
        return True

    def background(self, mask=MASK_ALL_BG):
        """
        Returns a list of background strings for the round
        """
        results = []
        if (mask & MASK_ROUND_ENDPOINTS) & self.earliest_end_time:
            results.append(u'Round %d could end as early as %s.' % (self.number,
                                                                    self.earliest_end_time.strftime("%H:%M")))
        if (mask & MASK_ROUND_ENDPOINTS) & self.latest_end_time:
            results.append(u'Round %d could end as late as %s.' % (self.number,
                                                                   self.latest_end_time.strftime("%H:%M")))
        if (mask & MASK_ROUND_ENDPOINTS) & self.final_year:
            results.append(u'Round %d will end after playing year %d.' % (self.number,
                                                                          self.final_year))
        # Shuffle the resulting list
        random.shuffle(results)
        return results

    def clean(self):
        # Must provide either both end times, or neither
        if self.earliest_end_time and not self.latest_end_time:
            raise ValidationError('Earliest end time specified without latest end time')
        if self.latest_end_time and not self.earliest_end_time:
            raise ValidationError('Latest end time specified without earliest end time')

    def get_absolute_url(self):
        return reverse('round_detail',
                       args=[str(self.tournament.id), str(self.number)])

    def __unicode__(self):
        return u'%s round %d' % (self.tournament, self.number)

class Game(models.Model):
    """
    A single game of Diplomacy, within a Round
    """
    # TODO Because we use game name in URLs, they must not contain spaces
    # TODO with our current URL scheme, we actually need game names to be unique
    # within the tournament - this is more restrictive than that
    name = models.CharField(max_length=20, unique=True)
    started_at = models.DateTimeField()
    is_finished = models.BooleanField(default=False)
    is_top_board = models.BooleanField(default=False)
    the_round = models.ForeignKey(Round, verbose_name='round')
    # TODO Use this
    power_assignment = models.CharField(max_length=1,
                                        verbose_name='Power assignment method',
                                        choices=POWER_ASSIGNS,
                                        default=RANDOM)

    class Meta:
        ordering = ['name']

    def is_dias(self):
        """
        Returns whether the game is Draws Include All Survivors
        """
        return self.the_round.dias

    def years_played(self):
        """
        Returns a list of years for which there are SC counts for this game
        """
        scs = self.centrecount_set.all()
        return sorted(list(set([sc.year for sc in scs])))

    def players(self, latest=True):
        """
        Returns a dict, keyed by power, of lists of players of that power
        If latest is True, only include the latest player of each power
        """
        powers = GreatPower.objects.all()
        gps = self.gameplayer_set.all().order_by('-first_year')
        retval = {}
        for power in powers:
            ps = gps.filter(power=power)
            if latest:
                ps = ps[0:1]
            retval[power] = [gp.player for gp in ps]
        return retval

    def news(self, include_game_name=False, mask=MASK_ALL_NEWS):
        """
        Returns a list of strings the describe the latest events in the game
        """
        if include_game_name:
            gn_str = ' in game %s' % self.name
        else:
            gn_str = ''
        if self.is_finished:
            # Just report the final result
            return [self.result_str(include_game_name)]
        player_dict = self.players(latest=True)
        centres_set = self.centrecount_set.order_by('-year')
        last_year = centres_set[0].year
        current_scs = centres_set.filter(year=last_year)
        results = []
        if (mask & MASK_BOARD_TOP) != 0:
            # Who's topping the board ?
            max_scs = current_scs.order_by('-count')[0].count
            first = current_scs.order_by('-count').filter(count=max_scs)
            first_str = ', '.join(['%s (%s)' % (player_dict[scs.power][0],
                                                scs.power.abbreviation) for scs in list(first)])
            results.append("Highest SC count%s is %d, for %s." % (gn_str, max_scs, first_str))
        if last_year > 1900:
            prev_scs = centres_set.filter(year=last_year-1)
        else:
            # We only look for differences, so just force no differences
            prev_scs = current_scs
        for scs in current_scs:
            power = scs.power
            prev = prev_scs.get(power=power)
            # Who gained 2 or more centres in the last year ?
            if (mask & MASK_GAINERS) != 0:
                if scs.count - prev.count > 1:
                    results.append("%s (%s) grew from %d to %d centres%s." % (player_dict[power][0],
                                                                              power.abbreviation,
                                                                              prev.count,
                                                                              scs.count,
                                                                              gn_str))
            # Who lost 2 or more centres in the last year ?
            if (mask & MASK_LOSERS) != 0:
                if prev.count - scs.count > 1:
                    results.append("%s (%s) shrank from %d to %d centres%s." % (player_dict[power][0],
                                                                                power.abbreviation,
                                                                                prev.count,
                                                                                scs.count,
                                                                                gn_str))
        if (mask & MASK_DRAW_VOTES) != 0:
            # What draw votes failed in the last year ?
            draws_set = self.drawproposal_set.order_by('-year')
            # TODO Lots of overlap with result_str()
            for d in draws_set:
                powers = d.powers()
                sz = len(powers)
                incl = []
                for power in powers:
                    # TODO This looks broken if there were replacements
                    game_player = self.gameplayer_set.filter(power=power).get()
                    incl.append('%s (%s)' % (game_player.player, power.abbreviation))
                incl_str = ', '.join(incl)
                if sz == 1:
                    d_str = u'Vote to concede to %s failed%s.' % (incl_str, gn_str)
                else:
                    d_str = 'Draw vote for %d-way between %s failed%s.' % (sz, incl_str, gn_str)
                results.append(d_str)
        if (mask & MASK_ELIMINATIONS) != 0:
            # Who has been eliminated so far, and when ?
            zeroes = centres_set.filter(count=0).reverse()
            while len(zeroes):
                scs = zeroes[0]
                power = scs.power
                zeroes = zeroes.exclude(power=power)
                results.append("%s (%s) was eliminated in %d%s." % (player_dict[power][0],
                                                                    power.abbreviation,
                                                                    scs.year,
                                                                    gn_str))
        # Shuffle the resulting list
        random.shuffle(results)
        return results

    def background(self, mask=MASK_ALL_BG):
        """
        Returns a list of strings that give background for the game
        """
        players_by_power = self.players(latest=True)
        results = []
        for c,players in players_by_power.iteritems():
            for p in players:
                results += p.background(c, mask=mask)
        # Shuffle the resulting list
        random.shuffle(results)
        return results

    def passed_draw(self):
        """
        Returns either a DrawProposal if a draw vote passed, or None.
        """
        # Did a draw proposal pass ?
        try:
            return self.drawproposal_set.filter(passed=True).get()
        except DrawProposal.DoesNotExist:
            return None

    def board_toppers(self):
        """
        Returns a list of CentreCounts for the current leader(s)
        """
        centres_set = self.centrecount_set.order_by('-year')
        last_year = centres_set[0].year
        current_scs = centres_set.filter(year=last_year)
        max_scs = current_scs.order_by('-count')[0].count
        first = current_scs.order_by('-count').filter(count=max_scs)
        return list(first)

    def neutrals(self, year=None):
        """How many neutral SCs are/were there ?"""
        if not year:
            year = self.final_year()
        scs = self.centrecount_set.filter(year=year)
        neutrals = TOTAL_SCS
        for sc in scs:
            neutrals -= sc.count
        return neutrals

    def final_year(self):
        """
        Returns the last complete year of the game, whether the game is completed or ongoing
        """
        return self.years_played()[-1]

    def soloer(self):
        """
        Returns either a GamePlayer if somebody soloed the game, or None
        """
        # Just order by SC count, and check the first (highest)
        scs = self.centrecount_set.order_by('-count')
        if scs[0].count >= WINNING_SCS:
            # TODO This looks like it fails if the soloer was a replacement player
            return self.gameplayer_set.filter(power=scs[0].power).get()
        return None

    def result_str(self, include_game_name=False):
        """
        Returns a string representing the game result, if any, or None
        """
        if include_game_name:
            gn_str = ' %s' % self.name
        else:
            gn_str = ''
        # Did a draw proposal pass ?
        draw = self.passed_draw()
        if draw:
            powers = draw.powers()
            sz = len(powers)
            if sz == 1:
                retval = u'Game%s conceded to ' % gn_str
            else:
                retval = u'Vote passed to end game%s as a %d-way draw between ' % (gn_str, sz)
            winners = []
            for power in powers:
                # TODO This looks broken if there were replacements
                game_player = self.gameplayer_set.filter(power=power).get()
                winners.append('%s (%s)' % (game_player.player, power.abbreviation))
            return retval + ', '.join(winners)
        # Did a power reach 18 (or more) centres ?
        soloer = self.soloer()
        if soloer:
            # TODO would be nice to include their SC count
            return u'Game%s won by %s (%s)' % (gn_str, soloer.player, soloer.power.abbreviation)
        # TODO Did the game get to the fixed endpoint ?
        if self.is_finished:
            player_dict = self.players(latest=True)
            toppers = self.board_toppers()
            first_str = ', '.join(['%s (%s)' % (player_dict[scs.power][0],
                                                scs.power.abbreviation) for scs in list(toppers)])
            return u'Game%s ended. Board top is %d centres, for %s' % (gn_str, scs.count, first_str)
        # Then it seems to be ongoing
        return None

    def save(self, *args, **kwargs):
        super(Game, self).save(*args, **kwargs)
        # Auto-create 1900 SC counts (unless they already exist)
        for power in GreatPower.objects.all():
            i, created = CentreCount.objects.get_or_create(power=power,
                                                           game=self,
                                                           year=FIRST_YEAR-1,
                                                           count=power.starting_centres)
            i.save()
        # Auto-create S1901M image (if it doesn't exist)
        i, created = GameImage.objects.get_or_create(game=self,
                                                     year=FIRST_YEAR,
                                                     season=SPRING,
                                                     phase=MOVEMENT,
                                                     image=S1901M_IMAGE)
        i.save()

    def get_absolute_url(self):
        return reverse('game_detail',
                       args=[str(self.the_round.tournament.id), self.name])

    def __unicode__(self):
        return self.name

class DrawProposal(models.Model):
    """
    A single draw or concession proposal in a game
    """
    game = models.ForeignKey(Game)
    year = models.PositiveSmallIntegerField(validators=[validate_year])
    season = models.CharField(max_length=1, choices=SEASONS)
    passed = models.BooleanField()
    proposer = models.ForeignKey(GreatPower, related_name='+')
    power_1 = models.ForeignKey(GreatPower, related_name='+')
    power_2 = models.ForeignKey(GreatPower, blank=True, null=True, related_name='+')
    power_3 = models.ForeignKey(GreatPower, blank=True, null=True, related_name='+')
    power_4 = models.ForeignKey(GreatPower, blank=True, null=True, related_name='+')
    power_5 = models.ForeignKey(GreatPower, blank=True, null=True, related_name='+')
    power_6 = models.ForeignKey(GreatPower, blank=True, null=True, related_name='+')
    power_7 = models.ForeignKey(GreatPower, blank=True, null=True, related_name='+')

    def draw_size(self):
        return len(self.powers())

    def powers(self):
        """
        Returns a list of powers included in the draw proposal.
        """
        retval = []
        for name, value in self.__dict__.iteritems():
            if name.startswith('power_'):
                if value:
                    retval.append(GreatPower.objects.get(pk=value))
        return retval

    def clean(self):
        # No skipping powers
        found_null = False
        for n in range(1,8):
            if not self.__dict__['power_%d_id' % n]:
                found_null = True
            elif found_null:
                raise ValidationError('Draw powers should go as early as possible')
        # Each power must be unique
        powers = set()
        for name, value in self.__dict__.iteritems():
            if value and name.startswith('power_'):
                if value in powers:
                    power = GreatPower.objects.get(pk=value)
                    raise ValidationError('%s present more than once' % power)
                powers.add(value)
        # Only one successful draw proposal
        if self.passed:
            try:
                p = DrawProposal.objects.filter(game=self.game, passed=True).get()
                if p != self:
                    raise ValidationError('Game already has a successful draw proposal')
            except DrawProposal.DoesNotExist:
                pass
        # No dead powers included
        # If DIAS, all alive powers must be included
        dias = self.game.is_dias()
        year = self.game.final_year()
        scs = self.game.centrecount_set.filter(year=year)
        for sc in scs:
            if sc.power in powers:
                if sc.count == 0:
                    raise ValidationError('Dead power %s included in proposal' % sc.power)
            else:
                if dias and sc.count > 0:
                    raise ValidationError('Missing alive power %s in DIAS game' % sc.power)

    def save(self, *args, **kwargs):
        super(CentreCount, self).save(*args, **kwargs)
        # Does this complete the game ?
        if self.passed:
            self.game.is_finished = True
            self.game.save()

    def __unicode__(self):
        return u'%s %d%s' % (self.game, self.year, self.season)

class RoundPlayer(models.Model):
    """
    A person who played a round in a tournament
    """
    player = models.ForeignKey(Player)
    the_round = models.ForeignKey(Round, verbose_name='round')
    score = models.FloatField(default=0.0)

    class Meta:
        ordering = ['player']

    def clean(self):
        # Player should already be in the tournament
        t = self.the_round.tournament
        tp = self.player.tournamentplayer_set.filter(tournament=t)
        if not tp:
            raise ValidationError('Player is not yet in the tournament')

    def __unicode__(self):
        return u'%s in %s' % (self.player, self.the_round)

class GamePlayer(models.Model):
    """
    A person who played a Great Power in a Game
    """
    player = models.ForeignKey(Player)
    game = models.ForeignKey(Game)
    power = models.ForeignKey(GreatPower, related_name='+')
    first_year = models.PositiveSmallIntegerField(default=FIRST_YEAR, validators=[validate_year])
    first_season = models.CharField(max_length=1, choices=SEASONS, default=SPRING)
    last_year = models.PositiveSmallIntegerField(blank=True, null=True, validators=[validate_year])
    last_season = models.CharField(max_length=1, choices=SEASONS, blank=True)
    score = models.FloatField(default=0.0)
    # What order did this player choose their GreatPower ?
    # 1 => first, 7 => seventh, 0 => assigned rather than chosen
    # TODO Use this
    # TODO Add validators
    power_choice_order = models.PositiveSmallIntegerField(default=1)

    def clean(self):
        # Player should already be in the tournament
        t = self.game.the_round.tournament
        tp = self.player.tournamentplayer_set.filter(tournament=t)
        if not tp:
            raise ValidationError('Player is not yet in the tournament')
        # Need either both or neither of last_year and last_season
        if self.last_season == '' and self.last_year:
            raise ValidationError('Final season played must also be specified')
        if self.last_season != '' and not self.last_year:
            raise ValidationError('Final year must be specified with final season')
        # Check for overlap with another player
        others = GamePlayer.objects.filter(game=self.game, power=self.power).exclude(player=self.player)
        # Ensure one player at a time
        for other in others:
            if self.first_year < other.first_year:
                we_were_first = True
            elif self.first_year == other.first_year:
                if self.first_season == other.first_season:
                    raise ValidationError()
                if self.first_season == SPRING:
                    we_were_first = True
                else:
                    we_were_first = False
            else:
                we_were_first = False
            if we_were_first:
                # Our term must finish before theirs started
                err_str = '%s is listed as playing %s in game %s from %s %d' % (other.player,
                                                                                power,
                                                                                other.first_season,
                                                                                other.first_year)
                if not self.last_year or self.last_year > other.first_year:
                    raise ValidationError(err_str)
                if self.last_year == other.first_year:
                    if self.last_season != SPRING or other.first_season != FALL:
                        raise ValidationError(err_str)
            else:
                # Their term must finish before ours started
                err_str = '%s is listed as still playing %s in game %s in %s %d' % (other.player,
                                                                                    power,
                                                                                    self.first_season,
                                                                                    self.first_year)
                if not other.last_year or other.last_year > self.first_year:
                    raise ValidationError(err_str)
                if other.last_year == self.first_year:
                    if other.last_season != SPRING or self.first_season != FALL:
                        raise ValidationError(err_str)
        # TODO Ensure no gaps - may have to be done elsewhere

    def __unicode__(self):
        return u'%s %s %s' % (self.game, self.player, self.power)

def file_location(instance, filename):
    """
    Function that determines where to store the file.
    """
    # TODO Probably want a separate directory for each tournament,
    #      containing a directory per game
    return 'games'

class GameImage(models.Model):
    """
    An image depicting a Game at a certain point.
    The year, season, phase together indicate the phase that is about to played.
    """
    game = models.ForeignKey(Game)
    year = models.PositiveSmallIntegerField(validators=[validate_year])
    season = models.CharField(max_length=1, choices=SEASONS, default=SPRING)
    phase = models.CharField(max_length=1, choices=PHASES, default=MOVEMENT)
    image = models.ImageField(upload_to=file_location)

    class Meta:
        unique_together = ('game', 'year', 'season', 'phase')
        ordering = ['game', 'year', '-season', 'phase']

    def turn_str(self):
        """
        Short string version of season/year/phase
        e.g. 'S1901M'
        """
        return u'%s%d%s' % (self.season, self.year, phase_str(self.phase))

    def clean(self):
        if self.season == SPRING and self.phase == ADJUSTMENTS:
            raise ValidationError('No adjustment phase in spring')

    def __unicode__(self):
        return u'%s %s image' % (self.game, self.turn_str())

class CentreCount(models.Model):
    """
    The number of centres owned by one power at the end of a given game year
    """
    power = models.ForeignKey(GreatPower, related_name='+')
    game = models.ForeignKey(Game)
    year = models.PositiveSmallIntegerField(validators=[validate_year_including_start])
    count = models.PositiveSmallIntegerField(validators=[validate_sc_count])

    class Meta:
        unique_together = ('power', 'game', 'year')

    def clean(self):
        # Is this for a year that is supposed to be played ?
        final_year = self.game.the_round.final_year
        if final_year and self.year > final_year:
                raise ValidationError('Games in this round end with %d' % final_year)
        # Not possible to more than double your count in one year
        # or to recover from an elimination
        try:
            prev = CentreCount.objects.filter(power=self.power, game=self.game, year=self.year-1).get()
            if self.count > 2 * prev.count:
                raise ValidationError('SC count for a power cannot more than double in a year')
            elif (prev.count == 0) and (self.count > 0):
                raise ValidationError('SC count for a power cannot increase from zero')
        except CentreCount.DoesNotExist:
            # We're either missing a year, or this is the first year - let that go
            pass

    def save(self, *args, **kwargs):
        super(CentreCount, self).save(*args, **kwargs)
        # Does this complete the game ?
        final_year = self.game.the_round.final_year
        if final_year and self.year == final_year:
            # Final game year has been played
            self.game.is_finished = True
            self.game.save()
        if self.count >= WINNING_SCS:
            # Somebody won the game
            self.game.is_finished = True
            self.game.save()

    def __unicode__(self):
        return u'%s %d %s %d' % (self.game, self.year, self.power.abbreviation, self.count)

class PlayerRanking(models.Model):
    """
    A tournament ranking for a player.
    Used to import background information from the WDD.
    """
    player = models.ForeignKey(Player)
    tournament = models.CharField(max_length=30)
    position = models.PositiveSmallIntegerField()
    year = models.PositiveSmallIntegerField()
    date = models.DateField(blank=True, null=True)
    title = models.CharField(max_length=30, blank=True)

    def __unicode__(self):
        pos = position_str(self.position)
        s = u'%s came %s at %s' % (self.player, pos, self.tournament)
        if self.tournament[-4:] != unicode(self.year):
            s += u' in %d' % self.year
        return s

class PlayerGameResult(models.Model):
    """
    One player's result for a tournament game.
    Used to import background information from the WDD.
    """
    tournament_name = models.CharField(max_length=20)
    game_name = models.CharField(max_length=20)
    player = models.ForeignKey(Player)
    power = models.ForeignKey(GreatPower, related_name='+')
    date = models.DateField()
    position = models.PositiveSmallIntegerField()
    position_equals = models.PositiveSmallIntegerField(blank=True, null=True)
    score = models.FloatField(blank=True, null=True)
    final_sc_count = models.PositiveSmallIntegerField(blank=True, null=True)
    result = models.CharField(max_length=2, choices=GAME_RESULT, blank=True)
    year_eliminated = models.PositiveSmallIntegerField(blank=True, null=True, validators=[validate_year])

    class Meta:
        unique_together = ('tournament_name', 'game_name', 'player', 'power')

    def __unicode__(self):
        return u'%s played %s in %s' % (self.player, self.power, self.game_name)

