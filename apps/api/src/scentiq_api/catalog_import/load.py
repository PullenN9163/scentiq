from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection, Cursor
from psycopg.types.json import Jsonb

from scentiq_api.catalog_import.merge import CanonicalCatalog, CanonicalFragrance
from scentiq_api.catalog_import.normalize import fold

DEMO_BRAND_IDS = tuple(UUID(f"01000000-0000-4000-8000-{index:012d}") for index in range(1, 4))
DEMO_FRAGRANCE_IDS = tuple(UUID(f"10000000-0000-4000-8000-{index:012d}") for index in range(1, 16))


@dataclass(frozen=True)
class LoadResult:
    run_id: UUID
    counts: dict[str, int]

    @property
    def catalog_changes(self) -> int:
        excluded = {"import_runs_inserted", "demo_fragrances_referenced"}
        return sum(value for key, value in self.counts.items() if key not in excluded)


def _slug(value: str) -> str:
    return fold(value).replace(" ", "-")


def _search_text(fragrance: CanonicalFragrance) -> str:
    return fold(
        " ".join(
            part for part in (fragrance.brand, fragrance.name, fragrance.concentration) if part
        )
    )


def _validate(catalog: CanonicalCatalog) -> None:
    limits = {
        "brand": 120,
        "name": 255,
        "concentration": 40,
        "gender": 10,
        "olfactory_family": 60,
        "product_line": 160,
        "image_url": 512,
    }
    for fragrance in catalog.fragrances:
        values = {
            "brand": fragrance.brand,
            "name": fragrance.name,
            "concentration": fragrance.concentration,
            "gender": fragrance.gender,
            "olfactory_family": fragrance.olfactory_family,
            "product_line": fragrance.product_line,
            "image_url": fragrance.image_url,
        }
        for field_name, value in values.items():
            if value is not None and len(value) > limits[field_name]:
                raise ValueError(
                    f"{field_name} exceeds {limits[field_name]} characters for {fragrance.id}"
                )
        for note in fragrance.notes:
            if len(note.name) > 100 or len(_slug(note.key)) > 100:
                raise ValueError(f"note exceeds 100 characters for {fragrance.id}: {note.name}")
        for accord in fragrance.accords:
            if len(accord.name) > 100 or len(_slug(accord.key)) > 100:
                raise ValueError(f"accord exceeds 100 characters for {fragrance.id}: {accord.name}")
        for perfumer in fragrance.perfumers:
            if len(perfumer.name) > 160 or len(_slug(perfumer.key)) > 160:
                raise ValueError(
                    f"perfumer exceeds 160 characters for {fragrance.id}: {perfumer.name}"
                )


_STAGING_SQL = """
CREATE TEMP TABLE stg_brands (
    slug text PRIMARY KEY, name text NOT NULL, country text
) ON COMMIT DROP;
CREATE TEMP TABLE stg_fragrances (
    id uuid PRIMARY KEY, brand_slug text NOT NULL, name text NOT NULL,
    concentration text, release_year integer, description text, image_url text,
    gender text, olfactory_family text, product_line text,
    rating_average numeric, rating_count integer, popularity_score integer,
    search_text text NOT NULL, longevity_score numeric, projection_level text
) ON COMMIT DROP;
CREATE TEMP TABLE stg_notes (slug text PRIMARY KEY, name text NOT NULL) ON COMMIT DROP;
CREATE TEMP TABLE stg_fragrance_notes (
    fragrance_id uuid, note_slug text, stage text, weight numeric,
    PRIMARY KEY (fragrance_id, note_slug, stage)
) ON COMMIT DROP;
CREATE TEMP TABLE stg_accords (slug text PRIMARY KEY, name text NOT NULL) ON COMMIT DROP;
CREATE TEMP TABLE stg_fragrance_accords (
    fragrance_id uuid, accord_slug text, weight numeric,
    PRIMARY KEY (fragrance_id, accord_slug)
) ON COMMIT DROP;
CREATE TEMP TABLE stg_seasons (
    fragrance_id uuid, season text, weight numeric,
    PRIMARY KEY (fragrance_id, season)
) ON COMMIT DROP;
CREATE TEMP TABLE stg_perfumers (slug text PRIMARY KEY, name text NOT NULL) ON COMMIT DROP;
CREATE TEMP TABLE stg_fragrance_perfumers (
    fragrance_id uuid, perfumer_slug text,
    PRIMARY KEY (fragrance_id, perfumer_slug)
) ON COMMIT DROP;
CREATE TEMP TABLE stg_community (
    fragrance_id uuid PRIMARY KEY, longevity_average numeric, longevity_votes integer,
    sillage_average numeric, sillage_votes integer, price_value_average numeric,
    price_value_votes integer, have_count integer, had_count integer, want_count integer,
    perceived_female integer, perceived_female_leaning integer, perceived_unisex integer,
    perceived_male_leaning integer, perceived_male integer, day_votes integer,
    night_votes integer, voters integer, captured_at timestamptz
) ON COMMIT DROP;
CREATE TEMP TABLE stg_similarities (
    fragrance_id uuid, similar_fragrance_id uuid, kind text, rank integer,
    up_votes integer, down_votes integer,
    PRIMARY KEY (fragrance_id, similar_fragrance_id, kind)
) ON COMMIT DROP;
CREATE TEMP TABLE stg_sources (
    id uuid PRIMARY KEY, fragrance_id uuid, source text, source_record_id text,
    source_url text, raw_name text, raw_brand text, rating_raw numeric,
    rating_scale numeric, rating_count integer, field_origins jsonb,
    UNIQUE (source, source_record_id)
) ON COMMIT DROP;
"""


def _copy(
    cursor: Cursor[Any], table: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]
) -> None:
    with cursor.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


def _brand_rows(catalog: CanonicalCatalog) -> Iterator[tuple[str, str, str | None]]:
    brands: dict[str, tuple[str, str | None]] = {}
    for fragrance in catalog.fragrances:
        slug = _slug(fragrance.brand_key)
        previous = brands.get(slug)
        if (
            previous is not None
            and previous[1] not in {None, fragrance.country}
            and fragrance.country
        ):
            raise ValueError(f"conflicting countries for brand {fragrance.brand}")
        brands[slug] = (
            previous[0] if previous else fragrance.brand,
            fragrance.country or (previous[1] if previous else None),
        )
    for slug, (name, country) in brands.items():
        yield slug, name, country


def _fragrance_rows(catalog: CanonicalCatalog) -> Iterator[tuple[Any, ...]]:
    for item in catalog.fragrances:
        yield (
            item.id,
            _slug(item.brand_key),
            item.name,
            item.concentration,
            item.release_year,
            item.description,
            item.image_url,
            item.gender,
            item.olfactory_family,
            item.product_line,
            item.rating_average,
            item.rating_count,
            item.popularity_score,
            _search_text(item),
            item.longevity_score,
            item.projection_level,
        )


def _stage_catalog(cursor: Cursor[Any], catalog: CanonicalCatalog) -> None:
    cursor.execute(_STAGING_SQL)
    _copy(cursor, "stg_brands", ("slug", "name", "country"), _brand_rows(catalog))
    _copy(
        cursor,
        "stg_fragrances",
        (
            "id",
            "brand_slug",
            "name",
            "concentration",
            "release_year",
            "description",
            "image_url",
            "gender",
            "olfactory_family",
            "product_line",
            "rating_average",
            "rating_count",
            "popularity_score",
            "search_text",
            "longevity_score",
            "projection_level",
        ),
        _fragrance_rows(catalog),
    )

    notes: dict[str, str] = {}
    note_links: dict[tuple[UUID, str, str], Decimal | None] = {}
    accords: dict[str, str] = {}
    accord_links: dict[tuple[UUID, str], Decimal] = {}
    perfumers: dict[str, str] = {}
    perfumer_links: set[tuple[UUID, str]] = set()
    for item in catalog.fragrances:
        for note in item.notes:
            slug = _slug(note.key)
            notes.setdefault(slug, note.name)
            note_links[(item.id, slug, note.stage)] = note.weight
        for accord in item.accords:
            slug = _slug(accord.key)
            accords.setdefault(slug, accord.name)
            accord_links[(item.id, slug)] = accord.weight
        for perfumer in item.perfumers:
            slug = _slug(perfumer.key)
            perfumers.setdefault(slug, perfumer.name)
            perfumer_links.add((item.id, slug))

    _copy(cursor, "stg_notes", ("slug", "name"), ((slug, name) for slug, name in notes.items()))
    _copy(
        cursor,
        "stg_fragrance_notes",
        ("fragrance_id", "note_slug", "stage", "weight"),
        ((*key, weight) for key, weight in note_links.items()),
    )
    _copy(
        cursor,
        "stg_accords",
        ("slug", "name"),
        ((slug, name) for slug, name in accords.items()),
    )
    _copy(
        cursor,
        "stg_fragrance_accords",
        ("fragrance_id", "accord_slug", "weight"),
        ((*key, weight) for key, weight in accord_links.items()),
    )
    _copy(
        cursor,
        "stg_perfumers",
        ("slug", "name"),
        ((slug, name) for slug, name in perfumers.items()),
    )
    _copy(
        cursor,
        "stg_fragrance_perfumers",
        ("fragrance_id", "perfumer_slug"),
        perfumer_links,
    )
    _copy(
        cursor,
        "stg_seasons",
        ("fragrance_id", "season", "weight"),
        (
            (item.id, season, weight)
            for item in catalog.fragrances
            for season, weight in item.seasons.items()
        ),
    )
    _copy(
        cursor,
        "stg_community",
        (
            "fragrance_id",
            "longevity_average",
            "longevity_votes",
            "sillage_average",
            "sillage_votes",
            "price_value_average",
            "price_value_votes",
            "have_count",
            "had_count",
            "want_count",
            "perceived_female",
            "perceived_female_leaning",
            "perceived_unisex",
            "perceived_male_leaning",
            "perceived_male",
            "day_votes",
            "night_votes",
            "voters",
            "captured_at",
        ),
        (
            (
                item.id,
                item.community.longevity_average,
                item.community.longevity_votes,
                item.community.sillage_average,
                item.community.sillage_votes,
                item.community.price_value_average,
                item.community.price_value_votes,
                item.community.have_count,
                item.community.had_count,
                item.community.want_count,
                item.community.perceived_female,
                item.community.perceived_female_leaning,
                item.community.perceived_unisex,
                item.community.perceived_male_leaning,
                item.community.perceived_male,
                item.community.day_votes,
                item.community.night_votes,
                item.community.voters,
                item.community.captured_at,
            )
            for item in catalog.fragrances
            if item.community is not None
        ),
    )
    _copy(
        cursor,
        "stg_similarities",
        ("fragrance_id", "similar_fragrance_id", "kind", "rank", "up_votes", "down_votes"),
        (
            (
                item.id,
                similarity.similar_fragrance_id,
                similarity.kind,
                similarity.rank,
                similarity.up_votes,
                similarity.down_votes,
            )
            for item in catalog.fragrances
            for similarity in item.similarities
        ),
    )
    _copy(
        cursor,
        "stg_sources",
        (
            "id",
            "fragrance_id",
            "source",
            "source_record_id",
            "source_url",
            "raw_name",
            "raw_brand",
            "rating_raw",
            "rating_scale",
            "rating_count",
            "field_origins",
        ),
        (
            (
                uuid4(),
                item.id,
                source.source,
                source.source_record_id,
                source.source_url,
                source.raw_name,
                source.raw_brand,
                source.rating_raw,
                source.rating_scale,
                source.rating_count,
                Jsonb(source.field_origins),
            )
            for item in catalog.fragrances
            for source in item.sources
        ),
    )


def _run(cursor: Cursor[Any], counts: dict[str, int], key: str, sql: str) -> None:
    cursor.execute(sql)
    counts[key] = cursor.rowcount


def _upsert_catalog(cursor: Cursor[Any], run_id: UUID, counts: dict[str, int]) -> None:
    cursor.execute(
        "SELECT count(*) FROM fragrances f JOIN stg_fragrances s ON s.id=f.id "
        "WHERE f.owner_user_id IS NOT NULL"
    )
    collision = cursor.fetchone()
    if collision and collision[0]:
        raise ValueError("catalog UUID collides with a member-owned fragrance")

    _run(
        cursor,
        counts,
        "brands_updated",
        "UPDATE brands b SET name=s.name, country=s.country, updated_at=now() "
        "FROM stg_brands s WHERE b.slug=s.slug AND b.owner_user_id IS NULL "
        "AND ROW(b.name,b.country) IS DISTINCT FROM ROW(s.name,s.country)",
    )
    _run(
        cursor,
        counts,
        "brands_inserted",
        "INSERT INTO brands (id,name,slug,country,owner_user_id) "
        "SELECT gen_random_uuid(),s.name,s.slug,s.country,NULL FROM stg_brands s "
        "WHERE NOT EXISTS (SELECT 1 FROM brands b WHERE b.slug=s.slug AND b.owner_user_id IS NULL)",
    )

    update_columns = (
        "brand_id",
        "name",
        "concentration",
        "release_year",
        "description",
        "image_url",
        "gender",
        "olfactory_family",
        "product_line",
        "rating_average",
        "rating_count",
        "popularity_score",
        "search_text",
        "longevity_score",
        "projection_level",
    )
    assignments = ",".join(
        f"{column}=" + ("b.id" if column == "brand_id" else f"s.{column}")
        for column in update_columns
    )
    target_row = ",".join(
        "f.brand_id" if column == "brand_id" else f"f.{column}" for column in update_columns
    )
    source_row = ",".join(
        "b.id" if column == "brand_id" else f"s.{column}" for column in update_columns
    )
    _run(
        cursor,
        counts,
        "fragrances_updated",
        "UPDATE fragrances f SET " + assignments + ",updated_at=now() FROM stg_fragrances s "
        "JOIN brands b ON b.slug=s.brand_slug AND b.owner_user_id IS NULL "
        "WHERE f.id=s.id AND f.owner_user_id IS NULL AND ROW("
        + target_row
        + ") IS DISTINCT FROM ROW("
        + source_row
        + ")",
    )
    _run(
        cursor,
        counts,
        "fragrances_inserted",
        "INSERT INTO fragrances "
        "(id,brand_id,owner_user_id,name,concentration,release_year,description,image_blob_path,"
        "image_url,gender,olfactory_family,product_line,rating_average,rating_count,"
        "popularity_score,search_text,longevity_score,projection_level) "
        "SELECT s.id,b.id,NULL,s.name,s.concentration,s.release_year,s.description,NULL,"
        "s.image_url,s.gender,s.olfactory_family,s.product_line,s.rating_average,s.rating_count,"
        "s.popularity_score,s.search_text,s.longevity_score,s.projection_level "
        "FROM stg_fragrances s JOIN brands b ON b.slug=s.brand_slug AND b.owner_user_id IS NULL "
        "WHERE NOT EXISTS (SELECT 1 FROM fragrances f WHERE f.id=s.id)",
    )

    for dimension in ("notes", "accords", "perfumers"):
        _run(
            cursor,
            counts,
            f"{dimension}_updated",
            f"UPDATE {dimension} d SET name=s.name FROM stg_{dimension} s "
            "WHERE d.slug=s.slug AND d.name IS DISTINCT FROM s.name",
        )
        _run(
            cursor,
            counts,
            f"{dimension}_inserted",
            f"INSERT INTO {dimension} (id,name,slug) "
            f"SELECT gen_random_uuid(),s.name,s.slug FROM stg_{dimension} s "
            f"WHERE NOT EXISTS (SELECT 1 FROM {dimension} d WHERE d.slug=s.slug)",
        )

    replacement_sql = (
        (
            "fragrance_notes",
            "stg_fragrance_notes",
            "fn",
            "fn.fragrance_id=s.fragrance_id AND n.slug=s.note_slug AND fn.note_id=n.id "
            "AND fn.stage=s.stage",
            "INSERT INTO fragrance_notes (fragrance_id,note_id,stage,weight) "
            "SELECT s.fragrance_id,n.id,s.stage,s.weight FROM stg_fragrance_notes s "
            "JOIN notes n ON n.slug=s.note_slug ON CONFLICT (fragrance_id,note_id,stage) "
            "DO UPDATE SET weight=excluded.weight "
            "WHERE fragrance_notes.weight IS DISTINCT FROM excluded.weight",
        ),
        (
            "fragrance_accords",
            "stg_fragrance_accords",
            "fa",
            "fa.fragrance_id=s.fragrance_id AND a.slug=s.accord_slug AND fa.accord_id=a.id",
            "INSERT INTO fragrance_accords (fragrance_id,accord_id,weight) "
            "SELECT s.fragrance_id,a.id,s.weight FROM stg_fragrance_accords s "
            "JOIN accords a ON a.slug=s.accord_slug ON CONFLICT (fragrance_id,accord_id) "
            "DO UPDATE SET weight=excluded.weight "
            "WHERE fragrance_accords.weight IS DISTINCT FROM excluded.weight",
        ),
        (
            "fragrance_perfumers",
            "stg_fragrance_perfumers",
            "fp",
            "fp.fragrance_id=s.fragrance_id AND p.slug=s.perfumer_slug AND fp.perfumer_id=p.id",
            "INSERT INTO fragrance_perfumers (fragrance_id,perfumer_id) "
            "SELECT s.fragrance_id,p.id FROM stg_fragrance_perfumers s "
            "JOIN perfumers p ON p.slug=s.perfumer_slug ON CONFLICT DO NOTHING",
        ),
    )
    joins = {
        "fragrance_notes": "JOIN notes n ON n.slug=s.note_slug",
        "fragrance_accords": "JOIN accords a ON a.slug=s.accord_slug",
        "fragrance_perfumers": "JOIN perfumers p ON p.slug=s.perfumer_slug",
    }
    for table, staging, alias, predicate, insert_sql in replacement_sql:
        _run(
            cursor,
            counts,
            f"{table}_deleted",
            f"DELETE FROM {table} {alias} USING stg_fragrances sf "
            f"WHERE {alias}.fragrance_id=sf.id AND NOT EXISTS "
            f"(SELECT 1 FROM {staging} s {joins[table]} WHERE {predicate})",
        )
        _run(cursor, counts, f"{table}_upserted", insert_sql)

    simple_children = (
        (
            "fragrance_seasons",
            "stg_seasons",
            "season",
            "weight",
            "INSERT INTO fragrance_seasons (fragrance_id,season,weight) "
            "SELECT fragrance_id,season,weight FROM stg_seasons "
            "ON CONFLICT (fragrance_id,season) DO UPDATE SET weight=excluded.weight "
            "WHERE fragrance_seasons.weight IS DISTINCT FROM excluded.weight",
        ),
        (
            "fragrance_similarities",
            "stg_similarities",
            "similar_fragrance_id,kind",
            "rank,up_votes,down_votes",
            "INSERT INTO fragrance_similarities "
            "(fragrance_id,similar_fragrance_id,kind,rank,up_votes,down_votes) "
            "SELECT fragrance_id,similar_fragrance_id,kind,rank,up_votes,down_votes "
            "FROM stg_similarities ON CONFLICT (fragrance_id,similar_fragrance_id,kind) "
            "DO UPDATE SET rank=excluded.rank,up_votes=excluded.up_votes,"
            "down_votes=excluded.down_votes "
            "WHERE ROW(fragrance_similarities.rank,fragrance_similarities.up_votes,"
            "fragrance_similarities.down_votes) IS DISTINCT FROM "
            "ROW(excluded.rank,excluded.up_votes,excluded.down_votes)",
        ),
    )
    for table, staging, keys, _values, insert_sql in simple_children:
        comparisons = " AND ".join(f"s.{key.strip()}=c.{key.strip()}" for key in keys.split(","))
        _run(
            cursor,
            counts,
            f"{table}_deleted",
            f"DELETE FROM {table} c USING stg_fragrances sf "
            "WHERE c.fragrance_id=sf.id AND NOT EXISTS "
            f"(SELECT 1 FROM {staging} s WHERE s.fragrance_id=c.fragrance_id AND {comparisons})",
        )
        _run(cursor, counts, f"{table}_upserted", insert_sql)

    _run(
        cursor,
        counts,
        "fragrance_occasions_deleted",
        "DELETE FROM fragrance_occasions o USING stg_fragrances s WHERE o.fragrance_id=s.id",
    )
    _run(
        cursor,
        counts,
        "fragrance_community_stats_deleted",
        "DELETE FROM fragrance_community_stats c USING stg_fragrances f "
        "WHERE c.fragrance_id=f.id AND NOT EXISTS "
        "(SELECT 1 FROM stg_community s WHERE s.fragrance_id=c.fragrance_id)",
    )
    community_columns = (
        "longevity_average,longevity_votes,sillage_average,sillage_votes,price_value_average,"
        "price_value_votes,have_count,had_count,want_count,perceived_female,"
        "perceived_female_leaning,perceived_unisex,perceived_male_leaning,perceived_male,"
        "day_votes,night_votes,voters,captured_at"
    )
    _run(
        cursor,
        counts,
        "fragrance_community_stats_upserted",
        "INSERT INTO fragrance_community_stats (fragrance_id," + community_columns + ") "
        "SELECT fragrance_id," + community_columns + " FROM stg_community "
        "ON CONFLICT (fragrance_id) DO UPDATE SET "
        + ",".join(f"{column}=excluded.{column}" for column in community_columns.split(","))
        + " WHERE ROW("
        + ",".join(f"fragrance_community_stats.{column}" for column in community_columns.split(","))
        + ") IS DISTINCT FROM ROW("
        + ",".join(f"excluded.{column}" for column in community_columns.split(","))
        + ")",
    )

    cursor.execute(
        "INSERT INTO fragrance_sources "
        "(id,fragrance_id,source,source_record_id,source_url,raw_name,raw_brand,rating_raw,"
        "rating_scale,rating_count,field_origins,import_run_id) "
        "SELECT id,fragrance_id,source,source_record_id,source_url,raw_name,raw_brand,rating_raw,"
        "rating_scale,rating_count,field_origins,%s FROM stg_sources "
        "ON CONFLICT (source,source_record_id) DO UPDATE SET "
        "fragrance_id=excluded.fragrance_id,source_url=excluded.source_url,raw_name=excluded.raw_name,"
        "raw_brand=excluded.raw_brand,rating_raw=excluded.rating_raw,rating_scale=excluded.rating_scale,"
        "rating_count=excluded.rating_count,field_origins=excluded.field_origins,"
        "import_run_id=excluded.import_run_id WHERE ROW("
        "fragrance_sources.fragrance_id,fragrance_sources.source_url,fragrance_sources.raw_name,"
        "fragrance_sources.raw_brand,fragrance_sources.rating_raw,fragrance_sources.rating_scale,"
        "fragrance_sources.rating_count,fragrance_sources.field_origins::jsonb) "
        "IS DISTINCT FROM ROW("
        "excluded.fragrance_id,excluded.source_url,excluded.raw_name,excluded.raw_brand,"
        "excluded.rating_raw,excluded.rating_scale,excluded.rating_count,"
        "excluded.field_origins::jsonb)",
        (run_id,),
    )
    counts["fragrance_sources_upserted"] = cursor.rowcount


def _purge_demo(cursor: Cursor[Any], counts: dict[str, int]) -> None:
    references = " OR ".join(
        (
            "EXISTS (SELECT 1 FROM user_collection x WHERE x.fragrance_id=f.id)",
            "EXISTS (SELECT 1 FROM wishlists x WHERE x.fragrance_id=f.id)",
            "EXISTS (SELECT 1 FROM recommendations x WHERE x.fragrance_id=f.id)",
            "EXISTS (SELECT 1 FROM recommendation_candidates x WHERE x.fragrance_id=f.id)",
            "EXISTS (SELECT 1 FROM layering_logs x WHERE x.primary_fragrance_id=f.id "
            "OR x.secondary_fragrance_id=f.id)",
        )
    )
    cursor.execute(
        f"SELECT count(*) FROM fragrances f WHERE f.id=ANY(%s) "
        f"AND f.owner_user_id IS NULL AND ({references})",
        (list(DEMO_FRAGRANCE_IDS),),
    )
    row = cursor.fetchone()
    counts["demo_fragrances_referenced"] = int(row[0]) if row else 0
    cursor.execute(
        f"DELETE FROM fragrances f WHERE f.id=ANY(%s) AND f.owner_user_id IS NULL "
        f"AND NOT ({references})",
        (list(DEMO_FRAGRANCE_IDS),),
    )
    counts["demo_fragrances_deleted"] = cursor.rowcount
    cursor.execute(
        "DELETE FROM brands b WHERE b.id=ANY(%s) AND b.owner_user_id IS NULL "
        "AND NOT EXISTS (SELECT 1 FROM fragrances f WHERE f.brand_id=b.id)",
        (list(DEMO_BRAND_IDS),),
    )
    counts["demo_brands_deleted"] = cursor.rowcount


def load_catalog(
    connection: Connection[Any],
    catalog: CanonicalCatalog,
    *,
    inputs: Mapping[str, Any],
    purge_demo_catalog: bool = False,
) -> LoadResult:
    _validate(catalog)
    # Imports own their dedicated operator connection and always start a top-level
    # transaction so ON COMMIT staging cleanup and all-or-nothing semantics hold.
    connection.commit()
    run_id = uuid4()
    counts: dict[str, int] = {"import_runs_inserted": 1}
    started_at = datetime.now(UTC)
    try:
        with connection.transaction(), connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO catalog_import_runs "
                "(id,started_at,status,inputs,counts) VALUES (%s,%s,'running',%s,%s)",
                (run_id, started_at, Jsonb(dict(inputs)), Jsonb({})),
            )
            if purge_demo_catalog:
                _purge_demo(cursor, counts)
            _stage_catalog(cursor, catalog)
            _upsert_catalog(cursor, run_id, counts)
            cursor.execute(
                "UPDATE catalog_import_runs SET "
                "finished_at=%s,status='succeeded',counts=%s WHERE id=%s",
                (datetime.now(UTC), Jsonb(counts), run_id),
            )
        return LoadResult(run_id, counts)
    except Exception as error:
        connection.rollback()
        with connection.transaction(), connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO catalog_import_runs "
                "(id,started_at,finished_at,status,inputs,counts) "
                "VALUES (%s,%s,%s,'failed',%s,%s)",
                (
                    run_id,
                    started_at,
                    datetime.now(UTC),
                    Jsonb(dict(inputs)),
                    Jsonb({"error_type": type(error).__name__}),
                ),
            )
        raise
