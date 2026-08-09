from uuid import UUID

from scentiq_api.repositories import FragranceRepository
from scentiq_api.schemas import (
    AccordResponse,
    FragranceDetail,
    FragranceSummary,
    NoteResponse,
    OccasionResponse,
    SeasonResponse,
)


class FragranceService:
    def __init__(self, repository: FragranceRepository) -> None:
        self._repository = repository

    def list(self) -> list[FragranceSummary]:
        return [FragranceSummary.model_validate(item) for item in self._repository.list()]

    def get(self, fragrance_id: str) -> FragranceDetail | None:
        try:
            parsed_id = UUID(fragrance_id)
        except ValueError:
            return None
        item = self._repository.get(parsed_id)
        if item is None:
            return None

        summary = FragranceSummary.model_validate(item)
        stage_order = {"top": 0, "middle": 1, "base": 2}
        notes = [
            NoteResponse(
                id=link.note.id,
                name=link.note.name,
                slug=link.note.slug,
                stage=link.stage,
            )
            for link in sorted(
                item.note_links,
                key=lambda link: (stage_order[link.stage], link.note.name),
            )
        ]
        accords = [
            AccordResponse(
                id=link.accord.id,
                name=link.accord.name,
                slug=link.accord.slug,
                weight=float(link.weight),
            )
            for link in sorted(item.accord_links, key=lambda link: link.accord.name)
        ]
        seasons = [
            SeasonResponse(season=link.season, weight=float(link.weight))
            for link in sorted(item.seasons, key=lambda link: link.season)
        ]
        occasions = [
            OccasionResponse(occasion=link.occasion, weight=float(link.weight))
            for link in sorted(item.occasions, key=lambda link: link.occasion)
        ]
        return FragranceDetail(
            **summary.model_dump(),
            description=item.description,
            notes=notes,
            accords=accords,
            seasons=seasons,
            occasions=occasions,
        )
