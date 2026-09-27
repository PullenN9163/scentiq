"""Catalog reads and private custom-fragrance creation."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from scentiq_api.catalog_import.normalize import fold
from scentiq_api.errors import conflict, not_found
from scentiq_api.models import Fragrance
from scentiq_api.repositories import FragranceRepository
from scentiq_api.schemas import (
    AccordResponse,
    CommunityResponse,
    FragranceCreateRequest,
    FragranceDetail,
    FragranceSummary,
    NoteResponse,
    OccasionResponse,
    PerfumerResponse,
    SeasonResponse,
    SourceResponse,
)

_STAGE_ORDER = {"top": 0, "middle": 1, "base": 2, "general": 3}


def to_fragrance_summary(item: Fragrance) -> FragranceSummary:
    top_accords = [
        link.accord.name
        for link in sorted(
            item.accord_links,
            key=lambda link: (-float(link.weight), link.accord.name.casefold()),
        )[:3]
    ]
    return FragranceSummary(
        id=item.id,
        name=item.name,
        concentration=item.concentration,
        release_year=item.release_year,
        image_blob_path=item.image_blob_path,
        image_url=item.image_url,
        gender=item.gender,
        olfactory_family=item.olfactory_family,
        rating_average=float(item.rating_average) if item.rating_average is not None else None,
        rating_count=item.rating_count,
        top_accords=top_accords,
        longevity_score=float(item.longevity_score) if item.longevity_score is not None else None,
        projection_level=item.projection_level,
        brand=item.brand,
        is_custom=item.owner_user_id is not None,
    )


class FragranceService:
    def __init__(self, repository: FragranceRepository) -> None:
        self._repository = repository

    def search(
        self,
        user_id: UUID,
        *,
        query: str | None = None,
        limit: int = 25,
        offset: int = 0,
        gender: str | None = None,
        family: str | None = None,
        season: str | None = None,
        accord: str | None = None,
        sort: str = "relevance",
    ) -> list[FragranceSummary]:
        return [
            to_fragrance_summary(item)
            for item in self._repository.search(
                user_id,
                query=query,
                limit=limit,
                offset=offset,
                gender=gender,
                family=family,
                season=season,
                accord=accord,
                sort=sort,
            )
        ]

    def get(self, user_id: UUID, fragrance_id: UUID) -> FragranceDetail:
        item = self._repository.get(user_id, fragrance_id)
        if item is None:
            # A private entry owned by someone else is indistinguishable from
            # one that does not exist.
            raise not_found("Fragrance not found")

        notes = [
            NoteResponse(
                id=link.note.id,
                name=link.note.name,
                slug=link.note.slug,
                stage=link.stage,
                weight=float(link.weight) if link.weight is not None else None,
            )
            for link in sorted(
                item.note_links,
                key=lambda link: (_STAGE_ORDER[link.stage], link.note.name),
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
        perfumers = [
            PerfumerResponse(
                id=link.perfumer.id,
                name=link.perfumer.name,
                slug=link.perfumer.slug,
            )
            for link in sorted(item.perfumer_links, key=lambda link: link.perfumer.name.casefold())
        ]
        community = None
        if item.community is not None and any(
            value is not None
            for value in (
                item.community.longevity_average,
                item.community.sillage_average,
                item.community.price_value_average,
                item.community.have_count,
                item.community.had_count,
                item.community.want_count,
                item.community.voters,
            )
        ):
            community = CommunityResponse(
                **{
                    column: (
                        float(value) if column.endswith("_average") and value is not None else value
                    )
                    for column in CommunityResponse.model_fields
                    if (value := getattr(item.community, column)) is not None
                }
            )
        similar = [
            to_fragrance_summary(similar_item)
            for similar_item in self._repository.similar(user_id, fragrance_id)
        ]
        ordered_sources = sorted(
            item.source_links,
            key=lambda link: (link.source, link.source_record_id),
        )
        sources = [
            SourceResponse(source=link.source, url=link.source_url) for link in ordered_sources
        ]
        return FragranceDetail(
            **to_fragrance_summary(item).model_dump(),
            description=item.description,
            product_line=item.product_line,
            notes=notes,
            accords=accords,
            seasons=seasons,
            occasions=occasions,
            perfumers=perfumers,
            community=community,
            similar=similar,
            sources=sources,
        )

    def create_custom(self, user_id: UUID, request: FragranceCreateRequest) -> FragranceSummary:
        """Create a fragrance private to this user.

        A second identical entry is refused rather than silently duplicated, so
        the user's own catalog stays usable.
        """
        duplicate = self._repository.find_custom_duplicate(
            user_id,
            brand_name=request.brand_name,
            name=request.name,
            concentration=request.concentration,
        )
        if duplicate is not None:
            raise conflict(
                "fragrance_exists",
                "You already have a custom fragrance with that brand, name and concentration",
            )

        brand = self._repository.find_or_create_custom_brand(user_id, request.brand_name)
        fragrance = Fragrance(
            brand_id=brand.id,
            owner_user_id=user_id,
            name=request.name,
            concentration=request.concentration,
            release_year=request.release_year,
            description=request.description,
            longevity_score=(
                Decimal(str(request.longevity_score))
                if request.longevity_score is not None
                else None
            ),
            projection_level=request.projection_level,
            search_text=fold(" ".join((brand.name, request.name, request.concentration))),
        )
        try:
            created = self._repository.add_custom(fragrance)
        except IntegrityError as error:
            # The partial unique index is the authority; a concurrent identical
            # create lands here rather than creating a duplicate.
            raise conflict(
                "fragrance_exists",
                "You already have a custom fragrance with that brand, name and concentration",
            ) from error

        created.brand = brand
        return to_fragrance_summary(created)
