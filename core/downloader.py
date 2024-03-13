import asyncio
import os
from asyncio import Queue

from loguru import logger

from core.alist import Alist
from core.alist.offline_download import TaskList
from core.mikan import MikanAnimeResource


class AlistDownloader:
    def __init__(self, alist: Alist) -> None:
        self.alist = alist

    def __group_resources(self, resources: list[MikanAnimeResource]):
        """group resources by anime name and season"""
        resource_group: dict[str, dict[str, list[MikanAnimeResource]]] = {}
        for resource in resources:
            if resource.anime_name not in resource_group:
                resource_group[resource.anime_name] = {}
            if resource.season not in resource_group[resource.anime_name]:
                resource_group[resource.anime_name][resource.season] = []
            resource_group[resource.anime_name][resource.season].append(resource)
        return resource_group

    async def run(self, new_res_q: Queue, downloading_res_q: Queue, download_path: str):
        first_run = True
        while True:
            if not first_run:
                await asyncio.sleep(10)
            new_resources = []
            while not new_res_q.empty():
                new_resources.append(await new_res_q.get())
            if new_resources:
                try:
                    downloading_resources = await self.download(
                        new_resources, download_path
                    )
                except Exception as e:
                    logger.error(f"Error when download: {e}")
                    continue
                for resource in downloading_resources:
                    await downloading_res_q.put(resource)
            first_run = False

    async def download(
        self, new_resources: list[MikanAnimeResource], download_path: str
    ):
        resrouce_group = self.__group_resources(new_resources)
        task_list = TaskList()
        for anime_name, season_group in resrouce_group.items():
            for season, season_resources in season_group.items():
                subfolder = os.path.join(anime_name, f"Season {season}")
                fin_path = os.path.join(download_path, subfolder)
                urls = [resource.torrent_url for resource in season_resources]
                try:
                    tmp_task_list = await self.alist.add_offline_download_task(
                        fin_path, urls
                    )
                except Exception as e:
                    logger.error(f"Error when add offline download task: {e}")
                    continue
                task_list = task_list + tmp_task_list

        success_resources = []
        for resource in new_resources:
            for task in task_list:
                if resource.torrent_url == task.url:
                    resource.set_download_task(task)
                    success_resources.append(resource)
                    logger.info(f"Start to download: {resource.resource_title}")
                    break
        return success_resources
