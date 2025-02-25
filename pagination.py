"""
Handles Pagination for any embeds
"""
import discord
from discord.ui import Button, View


class PaginationView(View):
    def __init__(self, embeds, timeout=60):  # after 60s the pagination ends
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.current_page = 0

    async def update_embed(self, interaction: discord.Interaction):
        # Updates the message with the current embed.
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary)
    async def first_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = 0
        await self.update_embed(interaction)

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.secondary)
    async def previous_page(self, interaction: discord.Interaction, button: Button):
        if self.current_page > 0:
            self.current_page -= 1
        await self.update_embed(interaction)

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.secondary)
    async def next_page(self, interaction: discord.Interaction, button: Button):
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
        await self.update_embed(interaction)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def last_page(self, interaction: discord.Interaction, button: Button):
        self.current_page = len(self.embeds) - 1
        await self.update_embed(interaction)
