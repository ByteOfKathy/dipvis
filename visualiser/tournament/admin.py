# Diplomacy Tournament Visualiser
# Copyright (C) 2014, 2016 Chris Brand
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
from django.db import transaction

from tournament.diplomacy.models.game_set import GameSet
from tournament.diplomacy.models.great_power import GreatPower
from tournament.diplomacy.models.set_power import SetPower
from tournament.diplomacy.models.supply_centre import SupplyCentre
from tournament.models import CentreCount, DrawProposal
from tournament.models import Game, GameImage, GamePlayer
from tournament.models import Round, RoundPlayer, DBNCoverage
from tournament.models import SeederBias, Series, SupplyCentreOwnership
from tournament.models import Tournament, TournamentPlayer
from tournament.players import Player, PlayerAward
from tournament.players import PlayerGameResult, PlayerRanking
from tournament.players import PlayerTournamentRanking

class CentreCountAdmin(admin.ModelAdmin):
    list_filter = ('game__the_round__tournament', 'power', 'game', 'year')

class DBNCoverageAdmin(admin.ModelAdmin):
    list_filter = ('tournament',)

class DrawProposalAdmin(admin.ModelAdmin):
    list_filter = ('game__the_round__tournament', 'passed', 'game', 'year')

class GamePlayerInline(admin.TabularInline):
    model = GamePlayer
    fieldsets = (
        (None, {
            'fields': ('player', 'power', 'score')
        }),
    )
    def get_extra(self, request, obj=None, **kwargs):
        # We're going to want 7 players
        return 7

class GameAdmin(admin.ModelAdmin):
    """Include GamePlayer, CentreCount, DrawProposal, and SCOwnership with Game"""
    fields = ['the_round', 'name', 'external_url', 'notes', 'is_top_board', 'started_at', 'is_finished']
    inlines = [GamePlayerInline]
    list_filter = ('the_round__tournament', 'name', 'is_finished')

class GameImageAdmin(admin.ModelAdmin):
    list_filter = ('game__the_round__tournament', 'game', 'year', 'season', 'phase')

class GamePlayerAdmin(admin.ModelAdmin):
    list_filter = ('game__the_round__tournament', 'power', 'game', 'player')

class SetPowerInline(admin.TabularInline):
    model = SetPower

    def get_extra(self, request, obj=None, **kwargs):
        if obj is not None:
            # Most likely we have the set we need
            return 0
        # We're going to want 7 set powers
        return 7

class GameSetAdmin(admin.ModelAdmin):
    """Include SetPower as part of GameSet"""
    inlines = [SetPowerInline]

class PlayerAdmin(admin.ModelAdmin):
    exclude = ('_wdd_name',)
    list_filter = ('first_name', 'last_name')

class PlayerAwardAdmin(admin.ModelAdmin):
    list_filter = ('player', 'tournament', 'name', 'power')

class PlayerGameResultAdmin(admin.ModelAdmin):
    list_filter = ('player', 'tournament_name', 'power', 'position', 'result')

class PlayerRankingAdmin(admin.ModelAdmin):
    list_filter = ('system', 'player')

class PlayerTournamentRankingAdmin(admin.ModelAdmin):
    list_filter = ('player', 'tournament', 'position', 'year', 'title')

class RoundAdmin(admin.ModelAdmin):
    list_filter = ('tournament',)
    ordering = ['tournament__name', 'start']

class RoundPlayerAdmin(admin.ModelAdmin):
    list_filter = ('the_round__tournament', 'the_round', 'player', 'game_count')

    # RoundPlayer.delete() needs to be called for each object
    def delete_queryset(self, request, queryset):
        with transaction.atomic():
            for obj in queryset:
                obj.delete()

class SCOwnershipAdmin(admin.ModelAdmin):
    list_filter = ('game__the_round__tournament', 'game', 'owner', 'year')

class SeederBiasAdmin(admin.ModelAdmin):
    list_filter = ('player1__tournament', )

class SeriesAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ["name"]}

class RoundInline(admin.StackedInline):
    model = Round
    extra = 4
    fieldsets = (
        (None, {
            'fields': ('start', 'scoring_system', 'dias')
        }),
        ('Round end options', {
            'classes': ('collapse',),
            'fields': ('final_year', 'earliest_end_time', 'latest_end_time')
        }),
    )

class TournamentAdmin(admin.ModelAdmin):
    """Include Round as part of Tournament"""
    inlines = [RoundInline]
    fields = (('name', 'format', 'location'),
              ('start_date', 'end_date'),
              ('seed_games', 'power_assignment'),
              ('tournament_scoring_system', 'round_scoring_system'),
              ('draw_secrecy', 'best_country_criterion'),
              ('is_published', 'delay_game_url_publication'),
              ('managers', 'editable', 'no_email'),
              'wdd_tournament_id')

class TournamentPlayerAdmin(admin.ModelAdmin):
    list_filter = ('tournament', 'player', 'location', 'unranked')

# Register models
admin.site.register(CentreCount, CentreCountAdmin)
admin.site.register(DBNCoverage, DBNCoverageAdmin)
admin.site.register(DrawProposal, DrawProposalAdmin)
admin.site.register(Game, GameAdmin)
admin.site.register(GameImage, GameImageAdmin)
admin.site.register(GamePlayer, GamePlayerAdmin)
admin.site.register(GameSet, GameSetAdmin)
admin.site.register(GreatPower)
admin.site.register(Player, PlayerAdmin)
admin.site.register(PlayerAward, PlayerAwardAdmin)
admin.site.register(PlayerGameResult, PlayerGameResultAdmin)
admin.site.register(PlayerRanking, PlayerRankingAdmin)
admin.site.register(PlayerTournamentRanking, PlayerTournamentRankingAdmin)
admin.site.register(Round, RoundAdmin)
admin.site.register(RoundPlayer, RoundPlayerAdmin)
admin.site.register(SeederBias, SeederBiasAdmin)
admin.site.register(Series, SeriesAdmin)
admin.site.register(SupplyCentre)
admin.site.register(SupplyCentreOwnership, SCOwnershipAdmin)
admin.site.register(Tournament, TournamentAdmin)
admin.site.register(TournamentPlayer, TournamentPlayerAdmin)
