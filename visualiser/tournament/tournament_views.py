# Diplomacy Tournament Visualiser
# Copyright (C) 2014, 2016-2019 Chris Brand
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

"""
Tournament Views for the Diplomacy Tournament Visualiser.
"""

import csv
from io import StringIO

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.forms.formsets import formset_factory
from django.http import HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from tournament.email import send_roll_call_emails

from tournament.forms import BasePlayerRoundScoreFormset
from tournament.forms import BasePrefsFormset
from tournament.forms import EnableCheckInForm
from tournament.forms import PlayerRoundScoreForm
from tournament.forms import PrefsForm
from tournament.forms import SeederBiasForm

from tournament.diplomacy.models.game_set import GameSet
from tournament.models import Tournament, Game, SeederBias
from tournament.models import TournamentPlayer, RoundPlayer, GamePlayer
from tournament.models import InvalidPreferenceList
from tournament.news import news

# Redirect times are specified in seconds
REFRESH_TIME = 60


def tournament_index(request):
    """Display a list of tournaments"""
    # We actually retrieve two separate lists, one of all published tournaments (visible to all)
    main_list = Tournament.objects.filter(is_published=True)
    # and a second list of unpublished tournaents visible to the current user
    if request.user.is_superuser:
        # All unpublished tournaments
        unpublished_list = Tournament.objects.filter(is_published=False)
    elif request.user.is_active:
        # All unpublished tournaments where the current user is listed as a manager
        unpublished_list = request.user.tournament_set.filter(is_published=False)
    else:
        # None at all
        unpublished_list = Tournament.objects.none()
    context = {'tournament_list': main_list, 'unpublished_list': unpublished_list}
    return render(request, 'tournaments/index.html', context)


# Tournament views


def get_visible_tournament_or_404(pk, user):
    """
    Get the specified Tournament object, if it exists,
    and check that it is visible to the user.
    If it doesn't exist or isn't visible, raise Http404.
    """
    t = get_object_or_404(Tournament, pk=pk)
    # Visible to all if published
    if t.is_published:
        return t
    # Also visible if the user is a manager for the tournament
    if user.is_active and t in user.tournament_set.all():
        return t
    # Superusers see all
    if user.is_superuser:
        return t
    # Default to not visible
    raise Http404


def get_modifiable_tournament_or_404(pk, user):
    """
    Get the specified Tournament object, if it exists,
    and check that it is visible to the user and editable.
    If it doesn't exist or isn't editable, raise Http404.
    """
    t = get_visible_tournament_or_404(pk, user)
    if t.editable:
        return t
    raise Http404


def tournament_simple(request, tournament_id, template):
    """Just render the specified template with the tournament"""
    t = get_visible_tournament_or_404(tournament_id, request.user)
    context = {'tournament': t}
    return render(request, 'tournaments/%s.html' % template, context)


def tournament_scores(request,
                      tournament_id,
                      refresh=False,
                      redirect_url_name='tournament_scores_refresh'):
    """Display scores of a tournament"""
    t = get_visible_tournament_or_404(tournament_id, request.user)
    tps = t.tournamentplayer_set.order_by('-score',
                                          'player__last_name',
                                          'player__first_name')
    rds = t.round_set.all()
    # Grab the tournament scores and positions and round scores, all "if it ended now"
    t_positions_and_scores, r_scores = t.positions_and_scores()
    # Construct a list of dicts with [rank, tournament player, round 1 player, ..., round n player, tournament score]
    scores = []
    for p in tps:
        rs = []
        for r in rds:
            try:
                rp = p.roundplayers().get(the_round=r)
            except RoundPlayer.DoesNotExist:
                # This player didn't play this round
                rs.append(None)
            else:
                rs.append(rp)
        row = {'rank': '%d' % t_positions_and_scores[p.player][0],
               'player': p,
               'rounds': rs,
               'score': t_positions_and_scores[p.player][1]}
        scores.append(row)
    # sort rows by position (they'll retain the alphabetic sorting if equal)
    scores.sort(key=lambda row: float(row['rank']))
    # After sorting, replace UNRANKED with suitable text
    for row in scores:
        row['rank'] = row['rank'].replace('%d' % Tournament.UNRANKED, _('Unranked'))
    context = {'tournament': t, 'scores': scores, 'rounds': rds}
    if refresh:
        context['refresh'] = True
        context['redirect_time'] = REFRESH_TIME
        context['redirect_url'] = reverse(redirect_url_name, args=(tournament_id,))
    return render(request, 'tournaments/scores.html', context)


def tournament_game_results(request,
                            tournament_id,
                            refresh=False,
                            redirect_url_name='tournament_game_results_refresh'):
    """Display the results of all the games of a tournament"""
    t = get_visible_tournament_or_404(tournament_id, request.user)
    tps = t.tournamentplayer_set.order_by('player__last_name', 'player__first_name')
    rds = t.round_set.all()
    rounds = [r.number() for r in rds]
    # Grab the games for each round
    round_games = {}
    for r in rds:
        round_games[r] = r.game_set.all()
    # Construct a list of dicts with tournament player and a list of gameplayer sets, one per round
    results = []
    for tp in tps:
        # All the games (in every tournament) this player has played in
        gps = tp.player.gameplayer_set.all()
        # Create a list of GamePlayers, indexed by Round
        rs = []
        for r in rds:
            # Create a list of GamePlayers for this Player and Round
            gs = gps.filter(game__the_round=r).distinct()
            rs.append(gs)
        row = {'tournament_player': tp,
               'rounds': rs}
        results.append(row)
    context = {'tournament': t, 'results': results, 'rounds': rounds}
    if refresh:
        context['refresh'] = True
        context['redirect_time'] = REFRESH_TIME
        context['redirect_url'] = reverse(redirect_url_name, args=(tournament_id,))
    return render(request, 'tournaments/game_results.html', context)


def tournament_best_countries(request,
                              tournament_id,
                              refresh=False,
                              redirect_url_name='tournament_best_countries_refresh'):
    """Display best countries of a tournament"""
    t = get_visible_tournament_or_404(tournament_id, request.user)
    # gps is a dict, keyed by power, of lists of all gameplayers,
    # sorted by best country criterion
    gps = t.best_countries(whole_list=True)
    # We have to just pick a set here. Avalon Hill is most common in North America
    set_powers = GameSet.objects.get(name='Avalon Hill').setpower_set.order_by('power')
    # TODO Sort set_powers alphabetically by translated power.name
    rows = []
    # Add a row at a time, containing the best remaining result for each power
    # The list for each power should be the same length
    while gps[set_powers[0].power]:
        row = []
        for p in set_powers:
            try:
                gp = gps[p.power].pop(0)
            except IndexError:
                gp = None
            row.append(gp)
        rows.append(row)
    context = {'tournament': t, 'powers': set_powers, 'rows': rows}
    if refresh:
        context['refresh'] = True
        context['redirect_time'] = REFRESH_TIME
        context['redirect_url'] = reverse(redirect_url_name, args=(tournament_id,))
    return render(request, 'tournaments/best_countries.html', context)


def tournament_background(request, tournament_id, as_ticker=False):
    """Display background info for a tournament"""
    t = get_visible_tournament_or_404(tournament_id, request.user)
    context = {'tournament': t, 'subject': 'Background', 'content': t.background()}
    if as_ticker:
        context['redirect_time'] = REFRESH_TIME
        context['redirect_url'] = reverse('tournament_ticker',
                                          args=(tournament_id,))
        return render(request, 'tournaments/info_ticker.html', context)
    return render(request, 'tournaments/info.html', context)


def tournament_news(request, tournament_id, as_ticker=False):
    """Display the latest news of a tournament"""
    t = get_visible_tournament_or_404(tournament_id, request.user)
    context = {'tournament': t, 'subject': 'News', 'content': news(t)}
    if as_ticker:
        context['redirect_time'] = REFRESH_TIME
        context['redirect_url'] = reverse('tournament_ticker',
                                          args=(tournament_id,))
        return render(request, 'tournaments/info_ticker.html', context)
    return render(request, 'tournaments/info.html', context)


def tournament_round(request, tournament_id):
    """Display details of the currently in-progress round of a tournament"""
    t = get_visible_tournament_or_404(tournament_id, request.user)
    r = t.current_round()
    if r:
        context = {'tournament': t, 'round': r}
        return render(request, 'rounds/detail.html', context)
    # TODO There must be a better way than this
    return HttpResponse("No round currently being played")


# TODO Name is confusing - sounds like it takes a round_num
@permission_required('tournament.change_roundplayer')
def round_scores(request, tournament_id):
    """Provide a form to enter each player's score for each round"""
    t = get_modifiable_tournament_or_404(tournament_id, request.user)
    PlayerRoundScoreFormset = formset_factory(PlayerRoundScoreForm,
                                              extra=0,
                                              formset=BasePlayerRoundScoreFormset)
    data = []
    # Go through each player in the Tournament
    for tp in t.tournamentplayer_set.all():
        current = {'tp': tp, 'player': tp.player, 'overall_score': tp.score}
        for rp in tp.roundplayers():
            r = rp.the_round
            round_num = r.number()
            current['round_%d' % round_num] = rp.score
            # Scores for any games in the round
            games = GamePlayer.objects.filter(player=tp.player,
                                              game__the_round=r).distinct()
            current['game_scores_%d' % round_num] = ', '.join([str(g.score) for g in games])
        data.append(current)
    formset = PlayerRoundScoreFormset(request.POST or None,
                                      tournament=t,
                                      initial=data)
    if formset.is_valid():
        for form in formset:
            tp = form.cleaned_data['tp']
            for r_name, value in form.cleaned_data.items():
                # Skip if no score was entered
                if not value:
                    continue
                # We're only interested in the round score fields
                if r_name.startswith('round_'):
                    # Extract the round number from the field name
                    i = int(r_name[6:])
                    # Find that Round
                    r = t.round_numbered(i)
                    # Update the score
                    RoundPlayer.objects.update_or_create(player=tp.player,
                                                         the_round=r,
                                                         defaults={'score': value})
                elif r_name == 'overall_score':
                    # Store the player's tournament score
                    tp.score = value
                    tp.save()
        # Redirect to the read-only version
        return HttpResponseRedirect(reverse('tournament_scores',
                                            args=(tournament_id,)))

    return render(request,
                  'tournaments/enter_scores.html',
                  {'tournament': t,
                   'formset': formset})


@permission_required('tournament.change_round')
def self_check_in_control(request, tournament_id):
    """Provide a form to control self-check-in for each round"""
    t = get_modifiable_tournament_or_404(tournament_id, request.user)
    round_set = t.round_set.all()
    enable_data = {}
    for r in round_set.all():
        enable_data['round_%d' % r.number()] = r.enable_check_in
    form = EnableCheckInForm(request.POST or None,
                             tournament=t,
                             initial=enable_data)
    if form.is_valid():
        for r_name, value in form.cleaned_data.items():
            # Extract the round number from the field name
            i = int(r_name[6:])
            # Find that Round
            rd = t.round_numbered(i)
            if (value is True) and not rd.enable_check_in:
                # send emails if not already sent
                if not rd.email_sent:
                    send_roll_call_emails(i, list(t.tournamentplayer_set.all()))
                    rd.email_sent = True
            rd.enable_check_in = value
            rd.save()
        # Redirect to the roll call page
        return HttpResponseRedirect(reverse('round_roll_call',
                                            args=(tournament_id, t.current_round().number())))

    return render(request,
                  'tournaments/self_check_in_control.html',
                  {'tournament': t,
                   'post_url': request.path_info,
                   'form': form})


@permission_required('tournament.add_preference')
def enter_prefs(request, tournament_id):
    """Provide a form to enter player country preferences"""
    t = get_modifiable_tournament_or_404(tournament_id, request.user)
    PrefsFormset = formset_factory(PrefsForm,
                                   extra=0,
                                   formset=BasePrefsFormset)
    formset = PrefsFormset(request.POST or None, tournament=t)
    if formset.is_valid():
        for form in formset:
            if form.has_changed():
                tp = form.tp
                ps = form.cleaned_data['prefs']
                # Set preferences for this TournamentPlayer
                tp.create_preferences_from_string(ps)
        # If all went well, re-direct
        return HttpResponseRedirect(reverse('tournament_detail',
                                            args=(tournament_id,)))
    return render(request,
                  'tournaments/enter_prefs.html',
                  {'tournament': t,
                   'formset': formset})


@permission_required('tournament.add_preference')
def upload_prefs(request, tournament_id):
    """Upload a CSV file to enter player country preferences"""
    t = get_modifiable_tournament_or_404(tournament_id, request.user)
    if request.method == 'GET':
        return render(request,
                      'tournaments/upload_prefs.html',
                      {'tournament': t})
    try:
        csv_file = request.FILES['csv_file']
        if csv_file.multiple_chunks():
            messages.error(request,
                           'Uploaded file is too big (%.2f MB)' % csv_file.size / (1024 * 1024))
            return HttpResponseRedirect(reverse('upload_prefs',
                                                args=(tournament_id,)))
        # TODO How do I know what charset to use?
        fp = StringIO(csv_file.read().decode('utf8'))
        reader = csv.DictReader(fp)
        for row in reader:
            try:
                tp = TournamentPlayer.objects.get(pk=row['Id'])
            except KeyError:
                messages.error(request, 'Failed to find player Id')
                return HttpResponseRedirect(reverse('upload_prefs',
                                                    args=(tournament_id,)))
            p = tp.player
            try:
                if p.first_name != row['First Name']:
                    messages.error(request, "Player first name doesn't match id")
                    return HttpResponseRedirect(reverse('upload_prefs',
                                                        args=(tournament_id,)))
            except KeyError:
                messages.error(request, 'Failed to find player First Name')
                return HttpResponseRedirect(reverse('upload_prefs',
                                                    args=(tournament_id,)))
            try:
                if p.last_name != row['Last Name']:
                    messages.error(request, "Player last name doesn't match id")
                    return HttpResponseRedirect(reverse('upload_prefs',
                                                        args=(tournament_id,)))
            except KeyError:
                messages.error(request, 'Failed to find player Last Name')
                return HttpResponseRedirect(reverse('upload_prefs',
                                                    args=(tournament_id,)))
            # Player data matches, so go ahead and parse the preferences
            try:
                ps = row['Preferences']
            except KeyError:
                messages.error(request, 'Failed to find player Preferences')
                return HttpResponseRedirect(reverse('upload_prefs',
                                                    args=(tournament_id,)))
            try:
                tp.create_preferences_from_string(ps)
            except InvalidPreferenceList:
                messages.error(request, 'Invalid preference string %s' % ps)
                return HttpResponseRedirect(reverse('upload_prefs',
                                                    args=(tournament_id,)))
    except Exception as e:
        messages.error(request, 'Unable to upload file: ' + repr(e))

    return HttpResponseRedirect(reverse('enter_prefs',
                                        args=(tournament_id,)))


def prefs_csv(request, tournament_id):
    """Download a template CSV file to enter player country preferences"""
    t = get_visible_tournament_or_404(tournament_id, request.user)
    # Want the default player order
    tps = t.tournamentplayer_set.all()
    # What fields we want to write
    headers = ['Id',
               'First Name',
               'Last Name',
               'Preferences',
              ]

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="%s_%d_prefs.csv"' % (t.name,
                                                                                  t.start_date.year)

    writer = csv.DictWriter(response, fieldnames=headers)
    writer.writeheader()
    # One row per player (row order and field order don't matter)
    for tp in tps:
        p = tp.player
        row_dict = {'Id': tp.id,
                    'First Name': p.first_name,
                    'Last Name': p.last_name,
                    'Preferences': tp.prefs_string(),
                   }
        # Write this player's row out
        writer.writerow(row_dict)

    return response


@permission_required('tournament.add_seederbias')
def seeder_bias(request, tournament_id):
    """Display or add SeederBias objects for the Tournament"""
    t = get_visible_tournament_or_404(tournament_id, request.user)
    sb_set = SeederBias.objects.filter(player1__tournament=t)
    form = SeederBiasForm(request.POST or None,
                          tournament=t)
    if request.method == 'POST':
        if t.is_finished() or not t.editable:
            raise Http404
        for k in request.POST.keys():
            if k.startswith('delete_'):
                # Extract the SeederBias pk from the button name
                pk = int(k[7:])
                SeederBias.objects.filter(pk=pk).delete()
                # Redirect back here to flush the POST data
                return HttpResponseRedirect(reverse('seeder_bias',
                                                    args=(tournament_id,)))
        if form.is_valid():
            form.save()
            # Redirect back here to flush the POST data
            return HttpResponseRedirect(reverse('seeder_bias',
                                                args=(tournament_id,)))
    context = {'tournament': t,
               'biases': sb_set,
               'form': form}
    return render(request, 'tournaments/seeder_bias.html', context)


def round_index(request, tournament_id):
    """Display a list of rounds of a tournament"""
    t = get_visible_tournament_or_404(tournament_id, request.user)
    the_list = t.round_set.all()
    context = {'tournament': t, 'round_list': the_list}
    return render(request, 'rounds/index.html', context)
