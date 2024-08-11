import time
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from ..config import Config


@click.command(
    help="Download anime using the anime provider for a specified range",
    short_help="Download anime",
)
@click.argument(
    "anime-title",
    required=True,
)
@click.option(
    "--episode-range",
    "-r",
    help="A range of episodes to download",
)
@click.option(
    "--highest_priority",
    "-h",
    help="Choose stream indicated as highest priority",
    is_flag=True,
)
@click.pass_obj
def download(config: "Config", anime_title, episode_range, highest_priority):
    from click import clear
    from rich import print
    from rich.progress import Progress
    from thefuzz import fuzz

    from ...AnimeProvider import AnimeProvider
    from ...libs.anime_provider.types import Anime
    from ...libs.fzf import fzf
    from ...Utility.downloader.downloader import downloader
    from ..utils.tools import exit_app
    from ..utils.utils import filter_by_quality, fuzzy_inquirer

    anime_provider = AnimeProvider(config.provider)

    translation_type = config.translation_type
    download_dir = config.downloads_dir

    # ---- search for anime ----
    with Progress() as progress:
        progress.add_task("Fetching Search Results...", total=None)
        search_results = anime_provider.search_for_anime(
            anime_title, translation_type=translation_type
        )
    if not search_results:
        print("Search results failed")
        input("Enter to retry")
        download(config, anime_title, episode_range, highest_priority)
        return
    search_results = search_results["results"]
    search_results_ = {
        search_result["title"]: search_result for search_result in search_results
    }

    if config.auto_select:
        search_result = max(
            search_results_.keys(), key=lambda title: fuzz.ratio(title, anime_title)
        )
        print("[cyan]Auto selecting:[/] ", search_result)
    else:
        choices = list(search_results_.keys())
        if config.use_fzf:
            search_result = fzf.run(choices, "Please Select title: ", "FastAnime")
        else:
            search_result = fuzzy_inquirer(
                choices,
                "Please Select title",
            )

    # ---- fetch anime ----
    with Progress() as progress:
        progress.add_task("Fetching Anime...", total=None)
        anime: Anime | None = anime_provider.get_anime(
            search_results_[search_result]["id"]
        )
    if not anime:
        print("Sth went wring anime no found")
        input("Enter to continue...")
        download(config, anime_title, episode_range, highest_priority)
        return

    episodes = anime["availableEpisodesDetail"][config.translation_type]
    if episode_range:
        episodes_start, episodes_end = episode_range.split("-")

    else:
        episodes_start, episodes_end = 0, len(episodes)
    for episode in range(round(float(episodes_start)), round(float(episodes_end))):
        try:
            episode = str(episode)
            if episode not in episodes:
                print(f"[cyan]Warning[/]: Episode {episode} not found, skipping")
                continue
            with Progress() as progress:
                progress.add_task("Fetching Episode Streams...", total=None)
                streams = anime_provider.get_episode_streams(
                    anime, episode, config.translation_type
                )
                if not streams:
                    print("No streams skipping")
                    continue
            # ---- fetch servers ----
            if config.server == "top":
                with Progress() as progress:
                    progress.add_task("Fetching top server...", total=None)
                    server = next(streams)
                stream_link = filter_by_quality(config.quality, server["links"])
                if not stream_link:
                    print("Quality not found")
                    input("Enter to continue")
                    continue
                link = stream_link["link"]
                episode_title = server["episode_title"]
            else:
                with Progress() as progress:
                    progress.add_task("Fetching servers", total=None)
                    # prompt for server selection
                    servers = {server["server"]: server for server in streams}
                servers_names = list(servers.keys())
                if config.use_fzf:
                    server = fzf.run(servers_names, "Select an link: ")
                else:
                    server = fuzzy_inquirer(
                        servers_names,
                        "Select link",
                    )
                stream_link = filter_by_quality(
                    config.quality, servers[server]["links"]
                )
                if not stream_link:
                    print("Quality not found")
                    continue
                link = stream_link["link"]

                episode_title = servers[server]["episode_title"]
            print(f"[purple]Now Downloading:[/] {search_result} Episode {episode}")

            downloader._download_file(
                link,
                anime["title"],
                episode_title,
                download_dir,
                True,
                config.format,
            )
        except Exception as e:
            print(e)
            time.sleep(1)
            print("Continuing")
            clear()
    print("Done Downloading")
    exit_app()
