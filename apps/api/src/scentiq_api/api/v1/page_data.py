from datetime import timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from scentiq_api.auth import AuthenticatedUser, CurrentUserDependency
from scentiq_api.repositories import (
    CollectionRepository,
    DiscoveryRepository,
    FragranceRepository,
    HybridJobRepository,
    InsightsRepository,
    LayeringRepository,
    UserRepository,
    WearLogRepository,
)
from scentiq_api.schemas import (
    CommunityResponse,
    DashboardPageResponse,
    FragrancePageResponse,
    LayeringPageResponse,
    OccasionResponse,
    SeasonResponse,
    WeekFragrance,
    WeekPageResponse,
)
from scentiq_api.services import (
    CollectionService,
    DiscoveryService,
    FragranceService,
    HybridJobService,
    InsightsService,
    LayeringService,
    ProfileService,
    RecommendationService,
    WearLogService,
    to_fragrance_summary,
)


def create_page_data_router(
    get_session: object,
    current_user: CurrentUserDependency,
    *,
    catalog_version: str,
    algorithm_version: str,
    max_age_seconds: int,
) -> APIRouter:
    router = APIRouter(prefix="/page-data", tags=["page-data"])

    def collection(session: Session) -> CollectionService:
        return CollectionService(CollectionRepository(session), FragranceRepository(session))

    def recommendations(session: Session) -> RecommendationService:
        return RecommendationService(
            HybridJobService(HybridJobRepository(session)),
            DiscoveryService(DiscoveryRepository(session)),
            LayeringService(LayeringRepository(session)),
            catalog_version=catalog_version,
            algorithm_version=algorithm_version,
            max_age=timedelta(seconds=max_age_seconds),
        )

    def wears(session: Session) -> WearLogService:
        return WearLogService(WearLogRepository(session), CollectionRepository(session))

    @router.get("/dashboard", response_model=DashboardPageResponse)
    def dashboard(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> DashboardPageResponse:
        me = ProfileService(UserRepository(session)).get(user.user_id)
        response = DashboardPageResponse(
            me=me,
            insights=InsightsService(InsightsRepository(session)).for_user(user.user_id),
            recent_wears=wears(session).list_for_user(user.user_id, limit=10),
        )
        session.commit()
        return response

    @router.get("/layering", response_model=LayeringPageResponse)
    def layering(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> LayeringPageResponse:
        response = LayeringPageResponse(
            collection=collection(session).list_for_user(user.user_id),
            recommendations=recommendations(session).get(user.user_id),
        )
        session.commit()
        return response

    @router.get("/week", response_model=WeekPageResponse)
    def week(
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> WeekPageResponse:
        me = ProfileService(UserRepository(session)).get(user.user_id)
        owned_ids = {
            item.fragrance_id
            for item in CollectionRepository(session).list_for_user(user.user_id)
            if item.status == "owned"
        }
        fragrances = FragranceRepository(session).get_many(user.user_id, owned_ids)
        response = WeekPageResponse(
            me=me,
            owned=[
                WeekFragrance(
                    **to_fragrance_summary(item).model_dump(),
                    seasons=[
                        SeasonResponse(season=link.season, weight=float(link.weight))
                        for link in item.seasons
                    ],
                    occasions=[
                        OccasionResponse(occasion=link.occasion, weight=float(link.weight))
                        for link in item.occasions
                    ],
                    community=(
                        CommunityResponse.model_validate(item.community, from_attributes=True)
                        if item.community is not None
                        else None
                    ),
                )
                for item in fragrances
            ],
        )
        session.commit()
        return response

    @router.get("/fragrances/{fragrance_id}", response_model=FragrancePageResponse)
    def fragrance(
        fragrance_id: UUID,
        session: Annotated[Session, Depends(get_session)],
        user: Annotated[AuthenticatedUser, Depends(current_user)],
    ) -> FragrancePageResponse:
        item = CollectionRepository(session).find_existing(user.user_id, fragrance_id)
        return FragrancePageResponse(
            fragrance=FragranceService(FragranceRepository(session)).get(
                user.user_id, fragrance_id
            ),
            collection_item=(collection(session).get(user.user_id, item.id) if item else None),
            recent_wears=wears(session).list_for_user(
                user.user_id,
                fragrance_id=fragrance_id,
                limit=10,
            ),
        )

    return router
