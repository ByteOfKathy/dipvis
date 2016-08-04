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

from django.contrib import admin
from tournament.models import *

class RoundInline(admin.StackedInline):
    model = Round
    extra = 4
    fieldsets = (
        (None, {
            'fields': ('number', 'scoring_system', 'dias')
        }),
        ('Round end options', {
            'classes': ('collapse',),
            'fields': ('final_year', 'earliest_end_time', 'latest_end_time')
        }),
    )

class TournamentPlayerInline(admin.TabularInline):
    model = TournamentPlayer
    extra = 7

class TournamentAdmin(admin.ModelAdmin):
    inlines = [RoundInline, TournamentPlayerInline]

class GamePlayerInline(admin.TabularInline):
    model = GamePlayer
    fieldsets = (
        (None, {
            'fields': ('player', 'power', 'score')
        }),
        ('Replacement player options', {
            'classes': ('collapse',),
            'fields': ('first_season', 'first_year')
        }),
        ('Replaced player options', {
            'classes': ('collapse',),
            'fields': ('last_season', 'last_year')
        }),
    )
    def get_extra(self, request, obj=None, **kwargs):
        if obj:
            # Replacement players are pretty rare
            # Let them click the button if needed
            return 0
        # We're going to want 7 players
        return 7

class CentreCountInline(admin.TabularInline):
    model = CentreCount
    extra = 7

class DrawProposalInline(admin.StackedInline):
    model = DrawProposal
    extra = 1
    fieldsets = (
        (None, {
            'fields': ('season', 'year', 'proposer', 'passed')
        }),
        ('Powers', {
            'fields': ('power_1', 'power_2', 'power_3', 'power_4', 'power_5', 'power_6', 'power_7')
        })
    )

class GameAdmin(admin.ModelAdmin):
    fields = ['the_round', 'name', 'is_top_board', 'started_at', 'is_finished']
    inlines = [GamePlayerInline, CentreCountInline, DrawProposalInline]

# Register models
admin.site.register(GreatPower)
admin.site.register(Player)
admin.site.register(ScoringSystem)
admin.site.register(DrawProposal)
admin.site.register(CentreCount)
admin.site.register(TournamentPlayer)
admin.site.register(Tournament, TournamentAdmin)
admin.site.register(Game, GameAdmin)
