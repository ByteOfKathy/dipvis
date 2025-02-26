# Diplomacy Tournament Visualiser
# Copyright (C) 2019 Chris Brand
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

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from tournament.diplomacy.models.game_set import GameSet
from tournament.diplomacy.models.great_power import GreatPower
from tournament.game_scoring import G_SCORING_SYSTEMS
from tournament.models import Tournament, Round, Game
from tournament.models import R_SCORING_SYSTEMS, T_SCORING_SYSTEMS
from tournament.models import TournamentPlayer, RoundPlayer, GamePlayer
from tournament.models import CentreCount, DrawProposal, FALL
from tournament.players import Player

class WddViewTests(TestCase):
    fixtures = ['game_sets.json']

    @classmethod
    def setUpTestData(cls):
        # Easy access to all the GreatPowers
        austria = GreatPower.objects.get(abbreviation='A')
        england = GreatPower.objects.get(abbreviation='E')
        france = GreatPower.objects.get(abbreviation='F')
        germany = GreatPower.objects.get(abbreviation='G')
        italy = GreatPower.objects.get(abbreviation='I')
        russia = GreatPower.objects.get(abbreviation='R')
        turkey = GreatPower.objects.get(abbreviation='T')

        now = timezone.now()

        # Published Tournament so it's visible to all
        cls.t = Tournament.objects.create(name='t1',
                                          start_date=now,
                                          end_date=now,
                                          round_scoring_system=R_SCORING_SYSTEMS[0].name,
                                          tournament_scoring_system=T_SCORING_SYSTEMS[0].name,
                                          draw_secrecy=Tournament.SECRET,
                                          is_published=True)
        # Two Rounds
        r1 = Round.objects.create(tournament=cls.t,
                                  scoring_system=G_SCORING_SYSTEMS[0].name,
                                  dias=False,
                                  start=cls.t.start_date)
        r2 = Round.objects.create(tournament=cls.t,
                                  scoring_system=G_SCORING_SYSTEMS[0].name,
                                  dias=True,
                                  start=cls.t.start_date + timedelta(hours=24),
                                  final_year=1907)
        # Two Games in the first Round, top board in the second
        g1 = Game.objects.create(name="R1G1",
                                 started_at=cls.t.start_date,
                                 the_round=r1,
                                 the_set=GameSet.objects.first())
        g2 = Game.objects.create(name="R1G2",
                                 started_at=cls.t.start_date,
                                 the_round=r1,
                                 the_set=GameSet.objects.first())
        g3 = Game.objects.create(name="TopBoard",
                                 started_at=cls.t.start_date + timedelta(hours=24),
                                 the_round=r2,
                                 the_set=GameSet.objects.first(),
                                 is_top_board=True)
        # Players, RoundPlayers, and GamePlayers
        p1 = Player.objects.create(first_name='Angela',
                                   last_name='Ampersand')
        p2 = Player.objects.create(first_name='Bobby',
                                   last_name='Bandersnatch')
        p3 = Player.objects.create(first_name='Cassandra',
                                   last_name='Cucumber')
        p4 = Player.objects.create(first_name='Derek',
                                   last_name='Dromedary')
        p5 = Player.objects.create(first_name='Ethel',
                                   last_name='Elephant')
        p6 = Player.objects.create(first_name='Frank',
                                   last_name='Frankfurter')
        p7 = Player.objects.create(first_name='Georgette',
                                   last_name='Grape')
        p8 = Player.objects.create(first_name='Harry',
                                   last_name='Heffalump')
        p9 = Player.objects.create(first_name='Iris',
                                   last_name='Ignoramus')
        p10 = Player.objects.create(first_name='Jake',
                                    last_name='Jalopy')
        p11 = Player.objects.create(first_name='Katrina',
                                    last_name='Kingpin')
        p12 = Player.objects.create(first_name='Lucas',
                                    last_name='Lemon')
        p13 = Player.objects.create(first_name='Margaret',
                                    last_name='Maleficent')
        p14 = Player.objects.create(first_name='Nigel',
                                    last_name='Notorious')
        TournamentPlayer.objects.create(player=p1,
                                        tournament=cls.t)
        RoundPlayer.objects.create(player=p1,
                                   the_round=r1)
        GamePlayer.objects.create(player=p1,
                                  game=g1,
                                  power=turkey)
        TournamentPlayer.objects.create(player=p2,
                                        tournament=cls.t)
        RoundPlayer.objects.create(player=p2,
                                   the_round=r1)
        RoundPlayer.objects.create(player=p2,
                                   the_round=r2)
        GamePlayer.objects.create(player=p2,
                                  game=g1,
                                  power=russia)
        GamePlayer.objects.create(player=p2,
                                  game=g3,
                                  power=italy)
        TournamentPlayer.objects.create(player=p3,
                                        tournament=cls.t)
        RoundPlayer.objects.create(player=p3,
                                   the_round=r1)
        GamePlayer.objects.create(player=p3,
                                  game=g2,
                                  power=austria)
        TournamentPlayer.objects.create(player=p4,
                                        tournament=cls.t)
        RoundPlayer.objects.create(player=p4,
                                   the_round=r1)
        RoundPlayer.objects.create(player=p4,
                                   the_round=r2)
        GamePlayer.objects.create(player=p4,
                                  game=g2,
                                  power=england)
        GamePlayer.objects.create(player=p4,
                                  game=g3,
                                  power=turkey)
        TournamentPlayer.objects.create(player=p5,
                                        tournament=cls.t)
        RoundPlayer.objects.create(player=p5,
                                   the_round=r1)
        GamePlayer.objects.create(player=p5,
                                  game=g1,
                                  power=italy)
        TournamentPlayer.objects.create(player=p6,
                                        tournament=cls.t)
        RoundPlayer.objects.create(player=p6,
                                   the_round=r1)
        RoundPlayer.objects.create(player=p6,
                                   the_round=r2)
        GamePlayer.objects.create(player=p6,
                                  game=g1,
                                  power=germany)
        GamePlayer.objects.create(player=p6,
                                  game=g3,
                                  power=france)
        TournamentPlayer.objects.create(player=p7,
                                        tournament=cls.t)
        RoundPlayer.objects.create(player=p7,
                                   the_round=r1)
        GamePlayer.objects.create(player=p7,
                                  game=g1,
                                  power=france)
        TournamentPlayer.objects.create(player=p8,
                                        tournament=cls.t)
        RoundPlayer.objects.create(player=p8,
                                   the_round=r1)
        RoundPlayer.objects.create(player=p8,
                                   the_round=r2)
        GamePlayer.objects.create(player=p8,
                                  game=g2,
                                  power=france)
        GamePlayer.objects.create(player=p8,
                                  game=g3,
                                  power=russia)
        TournamentPlayer.objects.create(player=p9,
                                        tournament=cls.t,
                                        unranked=True)
        RoundPlayer.objects.create(player=p9,
                                   the_round=r1)
        GamePlayer.objects.create(player=p9,
                                  game=g2,
                                  power=germany)
        TournamentPlayer.objects.create(player=p10,
                                        tournament=cls.t)
        RoundPlayer.objects.create(player=p10,
                                   the_round=r1)
        RoundPlayer.objects.create(player=p10,
                                   the_round=r2)
        GamePlayer.objects.create(player=p10,
                                  game=g2,
                                  power=italy)
        GamePlayer.objects.create(player=p10,
                                  game=g3,
                                  power=germany)
        TournamentPlayer.objects.create(player=p11,
                                        tournament=cls.t)
        RoundPlayer.objects.create(player=p11,
                                   the_round=r1)
        GamePlayer.objects.create(player=p11,
                                  game=g1,
                                  power=england)
        TournamentPlayer.objects.create(player=p12,
                                        tournament=cls.t)
        RoundPlayer.objects.create(player=p12,
                                   the_round=r1)
        RoundPlayer.objects.create(player=p12,
                                   the_round=r2)
        GamePlayer.objects.create(player=p12,
                                  game=g2,
                                  power=russia)
        GamePlayer.objects.create(player=p12,
                                  game=g3,
                                  power=austria)
        TournamentPlayer.objects.create(player=p13,
                                        tournament=cls.t)
        RoundPlayer.objects.create(player=p13,
                                   the_round=r1)
        GamePlayer.objects.create(player=p13,
                                  game=g1,
                                  power=austria)
        TournamentPlayer.objects.create(player=p14,
                                        tournament=cls.t)
        RoundPlayer.objects.create(player=p14,
                                   the_round=r1)
        RoundPlayer.objects.create(player=p14,
                                   the_round=r2)
        GamePlayer.objects.create(player=p14,
                                  game=g2,
                                  power=turkey)
        GamePlayer.objects.create(player=p14,
                                  game=g3,
                                  power=england)
        # CentreCounts and DrawProposals
        # One game ends in a solo
        CentreCount.objects.create(power=austria,
                                   game=g1,
                                   year=1903,
                                   count=0)
        CentreCount.objects.create(power=england,
                                   game=g1,
                                   year=1903,
                                   count=4)
        CentreCount.objects.create(power=france,
                                   game=g1,
                                   year=1903,
                                   count=5)
        CentreCount.objects.create(power=germany,
                                   game=g1,
                                   year=1903,
                                   count=7)
        CentreCount.objects.create(power=italy,
                                   game=g1,
                                   year=1903,
                                   count=4)
        CentreCount.objects.create(power=russia,
                                   game=g1,
                                   year=1903,
                                   count=10)
        CentreCount.objects.create(power=turkey,
                                   game=g1,
                                   year=1903,
                                   count=4)
        CentreCount.objects.create(power=austria,
                                   game=g1,
                                   year=1909,
                                   count=0)
        CentreCount.objects.create(power=england,
                                   game=g1,
                                   year=1909,
                                   count=0)
        CentreCount.objects.create(power=france,
                                   game=g1,
                                   year=1909,
                                   count=4)
        CentreCount.objects.create(power=germany,
                                   game=g1,
                                   year=1909,
                                   count=12)
        CentreCount.objects.create(power=italy,
                                   game=g1,
                                   year=1909,
                                   count=0)
        CentreCount.objects.create(power=russia,
                                   game=g1,
                                   year=1909,
                                   count=18)
        CentreCount.objects.create(power=turkey,
                                   game=g1,
                                   year=1909,
                                   count=0)
        # Another with an elimination and a draw
        dp = DrawProposal.objects.create(game=g2,
                                         year=1908,
                                         season=FALL,
                                         passed=False,
                                         proposer=germany)
        dp.drawing_powers.add(germany)
        dp.drawing_powers.add(france)
        dp.drawing_powers.add(england)
        dp = DrawProposal.objects.create(game=g2,
                                         year=1910,
                                         season=FALL,
                                         passed=True,
                                         proposer=france)
        dp.drawing_powers.add(england)
        dp.drawing_powers.add(france)
        CentreCount.objects.create(power=austria,
                                   game=g2,
                                   year=1908,
                                   count=3)
        CentreCount.objects.create(power=england,
                                   game=g2,
                                   year=1908,
                                   count=8)
        CentreCount.objects.create(power=france,
                                   game=g2,
                                   year=1908,
                                   count=7)
        CentreCount.objects.create(power=germany,
                                   game=g2,
                                   year=1908,
                                   count=7)
        CentreCount.objects.create(power=italy,
                                   game=g2,
                                   year=1908,
                                   count=2)
        CentreCount.objects.create(power=russia,
                                   game=g2,
                                   year=1908,
                                   count=4)
        CentreCount.objects.create(power=turkey,
                                   game=g2,
                                   year=1908,
                                   count=3)
        CentreCount.objects.create(power=austria,
                                   game=g2,
                                   year=1910,
                                   count=1)
        CentreCount.objects.create(power=england,
                                   game=g2,
                                   year=1910,
                                   count=12)
        CentreCount.objects.create(power=france,
                                   game=g2,
                                   year=1910,
                                   count=13)
        CentreCount.objects.create(power=germany,
                                   game=g2,
                                   year=1910,
                                   count=0)
        CentreCount.objects.create(power=italy,
                                   game=g2,
                                   year=1910,
                                   count=2)
        CentreCount.objects.create(power=russia,
                                   game=g2,
                                   year=1910,
                                   count=3)
        CentreCount.objects.create(power=turkey,
                                   game=g2,
                                   year=1910,
                                   count=3)
        # Top board ends after 1907
        CentreCount.objects.create(power=austria,
                                   game=g3,
                                   year=1907,
                                   count=7)
        CentreCount.objects.create(power=england,
                                   game=g3,
                                   year=1907,
                                   count=0)
        CentreCount.objects.create(power=france,
                                   game=g3,
                                   year=1907,
                                   count=6)
        CentreCount.objects.create(power=germany,
                                   game=g3,
                                   year=1907,
                                   count=4)
        CentreCount.objects.create(power=italy,
                                   game=g3,
                                   year=1907,
                                   count=6)
        CentreCount.objects.create(power=russia,
                                   game=g3,
                                   year=1907,
                                   count=4)
        CentreCount.objects.create(power=turkey,
                                   game=g3,
                                   year=1907,
                                   count=7)

    def test_classification(self):
        response = self.client.get(reverse('csv_classification', args=(self.t.pk,)))
        self.assertEqual(response.status_code, 200)

    def test_classification_no_top_board(self):
        # Switch the top board to a regular board
        g = Game.objects.get(is_top_board=True)
        g.is_top_board=False
        g.save()
        response = self.client.get(reverse('csv_classification', args=(self.t.pk,)))
        self.assertEqual(response.status_code, 200)
        # Clean up
        g.is_top_board=True
        g.save()

    def test_boards(self):
        response = self.client.get(reverse('csv_boards', args=(self.t.pk,)))
        self.assertEqual(response.status_code, 200)

