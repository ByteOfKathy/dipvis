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
Player Views for the Diplomacy Tournament Visualiser.
"""

import csv
from io import StringIO

from django.contrib import messages
from django.contrib.auth.decorators import permission_required
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views import generic

from tournament.players import Player, add_player_bg, validate_wdd_player_id

# Player views


class PlayerIndexView(generic.ListView):
    """Player index"""
    model = Player
    paginate_by = 25
    template_name = 'players/index.html'
    context_object_name = 'player_list'


def player_detail(request, pk):
    """Details of a single player"""
    player = get_object_or_404(Player, pk=pk)
    if request.method == 'POST':
        # Technically, we should check permissions here,
        # but the impact of not doing so is minor
        add_player_bg(player)
        # Redirect back here to flush the POST data
        return HttpResponseRedirect(reverse('player_detail',
                                            args=(pk,)))
    return render(request,
                  'players/detail.html',
                  {'player': player})


@permission_required('tournament.add_player')
def upload_players(request):
    """Upload a CSV file to add Players"""
    if request.method == 'GET':
        return render(request,
                      'players/upload_players.html')

    count = 0
    try:
        csv_file = request.FILES['csv_file']
        if csv_file.multiple_chunks():
            messages.error(request,
                           'Uploaded file is too big (%.2f MB)' % csv_file.size / (1024 * 1024))
            return HttpResponseRedirect(reverse('upload_players'))
        # TODO How do I know what charset to use?
        fp = StringIO(csv_file.read().decode('utf8'))
        reader = csv.DictReader(fp)
        for row in reader:
            try:
                first_name = row['First Name'].strip()
            except KeyError:
                messages.error(request, 'Failed to find column First Name')
                return HttpResponseRedirect(reverse('upload_players'))

            try:
                last_name = row['Last Name'].strip()
            except KeyError:
                messages.error(request, 'Failed to find column Last Name')
                return HttpResponseRedirect(reverse('upload_players'))

            # All the other columns are optional
            try:
                email = row['Email Address'].strip()
            except KeyError:
                email = ''
            else:
                if len(email) > 0:
                    try:
                        validate_email(email)
                    except ValidationError:
                        messages.warning(request, 'Email address for %s %s is invalid - ignored' % (first_name, last_name))
                        email = ''

            try:
                bs_un = row['Backstabbr Username'].strip()
            except KeyError:
                bs_un = None

            # Accept either WDD Id or WDD URL
            # If we have a valid WDD Id, ignore WDD URL
            try:
                wdd_id = row['WDD Id'].strip()
            except KeyError:
                wdd_id = None
            else:
                try:
                    wdd_id = int(wdd_id)
                except ValueError:
                    if len(wdd_id):
                        messages.warning(request, 'WDD Id for %s %s is invalid - ignored' % (first_name, last_name))
                    wdd_id = None
                else:
                    try:
                        validate_wdd_player_id(wdd_id)
                    except ValidationError:
                        messages.warning(request, 'WDD Id for %s %s is invalid - ignored' % (first_name, last_name))
                        wdd_id = None

            if wdd_id is None:
                try:
                    wdd_url = row['WDD URL'].strip()
                except KeyError:
                    wdd_url = None
                else:
                    if len(wdd_url) > 0:
                        wdd_id = int(wdd_url.rpartition('id_player=')[-1])
                        try:
                            validate_wdd_player_id(wdd_id)
                        except ValidationError:
                            messages.warning(request, 'WDD URL for %s %s is invalid - ignored' % (first_name, last_name))
                            wdd_id = None

            # Add the Player
            p, created = Player.objects.update_or_create(first_name=first_name,
                                                         last_name=last_name,
                                                         defaults={'email': email,
                                                                   'backstabbr_username': bs_un,
                                                                   'wdd_player_id': wdd_id})
            if created:
                messages.info(request, 'Player %s %s added' % (first_name, last_name))
                count += 1
            else:
                # Add missing info and flag mismatches
                new_info = []
                if len(email) > 0:
                    if len(p.email) > 0:
                        if p.email != email:
                            messages.warning(request, 'Player %s %s already exists with a different email address' % (first_name, last_name))
                    else:
                        # Add the email address
                        p.email = email
                        new_info.append('email address')
                if bs_un is not None and len(bs_un) > 0:
                    if len(p.backstabbr_username) > 0:
                        if p.backstabbr_username != bs_un:
                            messages.warning(request, 'Player %s %s already exists with a different Backstabbr username' % (first_name, last_name))
                    else:
                        # Add the username
                        p.backstabbr_username = bs_un
                        new_info.append('Backstabbr username')
                if wdd_id is not None:
                    if p.wdd_player_id:
                        if p.wdd_player_id != wdd_id:
                            messages.warning(request, 'Player %s %s already exists with a different WDD Id' % (first_name, last_name))
                    else:
                        # Add the WDD id
                        p.wdd_player_id = wdd_id
                        new_info.append('WDD id')
                if len(new_info):
                    p.save()
                    messages.info(request, 'Player %s %s already exists - added %s' % (first_name, last_name, ', '.join(new_info)))
                else:
                    messages.info(request, 'Player %s %s already exists - skipped' % (first_name, last_name))

    except Exception as e:
        messages.error(request, 'Unable to upload file: ' + repr(e))

    messages.success(request, 'Added %d player(s)' % count)

    return HttpResponseRedirect(reverse('upload_players'))
