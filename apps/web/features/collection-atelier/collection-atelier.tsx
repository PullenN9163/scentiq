"use client";

import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ArrowDownUp, Plus, Search, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState, useTransition } from "react";
import { toast } from "sonner";

import { AccordStrip } from "@/components/atelier/accord-strip";
import { Button } from "@/components/atelier/button";
import { Chip } from "@/components/atelier/chip";
import { FragranceCard, type QuickAction } from "@/components/atelier/fragrance-card";
import { plateFragrance } from "@/components/atelier/plate";
import { SegmentedControl } from "@/components/atelier/segmented-control";
import { Sheet } from "@/components/atelier/sheet";
import { AtelierEmpty } from "@/components/atelier/states";
import { AddFragranceDialog } from "@/features/collection/add-fragrance-dialog";
import { BlendVial } from "@/features/blend/blend-vial";
import { useRegisterFragranceList } from "@/features/fragrance/fragrance-list-context";
import { WearLogSheet } from "@/features/fragrance/wear-log-sheet";
import { ACCORD_LABELS, accordFor } from "@/lib/accord";
import { idleState } from "@/lib/action-state";
import { motionTokens } from "@/lib/motion";
import { cn } from "@/lib/utils";
import { updateCollectionItem } from "@/lib/server/actions";
import type { CollectionItem, FragranceSummary, OwnershipType, WeightedSlice } from "@/types/api";
import type { SavedLayeringStack } from "@/types/layering";

import { DEFAULT_FILTERS, SORT_LABELS, accordsPresent, applyFilters, segmentItems, statusLine, type CollectionFilters, type Segment, type SortKey } from "./collection-filters";
import styles from "./collection-atelier.module.css";

const FORMATS: [OwnershipType, string][] = [["bottle", "Bottle"], ["decant", "Decant"], ["sample", "Sample"]];

/**
 * The Atelier Collection: Shelf, Wishlist and Blends. Filtering and sorting
 * stay client-side over the fetched collection, as in CollectionView.
 */
export function CollectionAtelier({
  items,
  catalog,
  tasteAccords,
  saved,
  initialSegment = "shelf",
}: {
  items: CollectionItem[];
  catalog: FragranceSummary[];
  /** `insights.accords`; null or empty hides the taste strip. */
  tasteAccords: WeightedSlice[] | null;
  /** Saved blends; null when they could not be loaded. */
  saved: SavedLayeringStack[] | null;
  initialSegment?: Segment;
}) {
  const router = useRouter();
  const [segment, setSegment] = useState<Segment>(initialSegment);
  const [filters, setFilters] = useState<CollectionFilters>(DEFAULT_FILTERS);
  const [draftFormats, setDraftFormats] = useState<OwnershipType[]>([]);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [wearItem, setWearItem] = useState<CollectionItem | null>(null);
  const [pending, startTransition] = useTransition();

  const owned = items.filter((item) => item.status === "owned");
  const wishlist = items.filter((item) => item.status === "wishlist");
  const base = segmentItems(items, segment, filters.finished);
  const visible = useMemo(() => applyFilters(base, filters), [base, filters]);
  const accordChoices = accordsPresent(segment === "wishlist" ? wishlist : owned);
  const filtered = filters.query.trim() !== "" || filters.accords.length > 0 || filters.formats.length > 0;
  useRegisterFragranceList(segment === "blends" ? [] : visible.map((item) => item.fragrance.id));

  function changeSegment(next: Segment) {
    setSegment(next);
    setFilters((current) => ({ ...DEFAULT_FILTERS, sort: current.sort }));
    const url = new URL(window.location.href);
    if (next === "shelf") url.searchParams.delete("segment"); else url.searchParams.set("segment", next);
    window.history.replaceState(window.history.state, "", url);
  }

  function toggleAccord(key: CollectionFilters["accords"][number]) {
    setFilters((current) => ({ ...current, accords: current.accords.includes(key) ? current.accords.filter((value) => value !== key) : [...current.accords, key] }));
  }

  function own(item: CollectionItem) {
    const form = new FormData();
    form.set("item_id", item.id);
    form.set("ownership_type", item.ownership_type);
    form.set("status", "owned");
    form.set("remaining_ml", item.remaining_ml?.toString() ?? "");
    form.set("purchase_price", item.purchase_price ?? "");
    form.set("user_rating", item.user_rating?.toString() ?? "");
    startTransition(async () => {
      const result = await updateCollectionItem(idleState, form);
      if (result.status === "error") { toast.error(result.message ?? "Could not move it to your shelf. Try again."); return; }
      toast.success("On your shelf");
      router.refresh();
    });
  }

  function actionsFor(item: CollectionItem): QuickAction[] {
    const layer = { label: "Layer it", href: `/layering?a=${item.fragrance.id}` };
    if (item.status === "wishlist") return [{ label: "I own this", onSelect: () => own(item), disabled: pending }, layer];
    if (item.status === "owned") return [{ label: "Wear it", onSelect: () => setWearItem(item) }, layer];
    return [layer];
  }

  const clearFilters = () => setFilters((current) => ({ ...DEFAULT_FILTERS, sort: current.sort }));

  return (
    <div className="at-page">
      <header className={styles.header}>
        <h1 className={styles.title}>Collection</h1>
        <SegmentedControl<Segment>
          label="Collection view"
          value={segment}
          onChange={changeSegment}
          segments={[
            { value: "shelf", label: "Shelf", count: owned.length },
            { value: "wishlist", label: "Wishlist", count: wishlist.length },
            { value: "blends", label: "Blends", count: saved?.length ?? 0 },
          ]}
        />
        <Button variant="outline" className={styles.add} onClick={() => setAddOpen(true)}><Plus aria-hidden="true" />Add fragrance</Button>
      </header>

      {segment !== "blends" ? (
        <>
          <div className={styles.toolbar}>
            <label className={styles.search}>
              <Search aria-hidden="true" />
              <span className="sr-only">Search {segment === "shelf" ? "your shelf" : "your wishlist"}</span>
              <input type="search" value={filters.query} placeholder="Search name or house" onChange={(event) => setFilters((current) => ({ ...current, query: event.target.value }))} />
            </label>
            <div className={styles.chips} role="group" aria-label="Filter by accord">
              {accordChoices.map((key) => <Chip key={key} variant="choice" pressed={filters.accords.includes(key)} onClick={() => toggleAccord(key)}>{ACCORD_LABELS[key]}</Chip>)}
              {segment === "shelf" ? <Chip variant="choice" pressed={filters.finished} onClick={() => setFilters((current) => ({ ...current, finished: !current.finished }))}>Finished</Chip> : null}
            </div>
            <div className={styles.toolbarEnd}>
              <Button variant="soft" size="sm" onClick={() => { setDraftFormats(filters.formats); setFiltersOpen(true); }}>
                <SlidersHorizontal aria-hidden="true" />Filters{filters.formats.length ? ` · ${filters.formats.length}` : ""}
              </Button>
              <DropdownMenu.Root modal={false}>
                <DropdownMenu.Trigger asChild>
                  <Button variant="soft" size="sm" aria-label={`Sort: ${SORT_LABELS[filters.sort]}`}><ArrowDownUp aria-hidden="true" /><span className={styles.sortLabel}>{SORT_LABELS[filters.sort]}</span></Button>
                </DropdownMenu.Trigger>
                <DropdownMenu.Portal>
                  <DropdownMenu.Content className={styles.menu} align="end" sideOffset={6} collisionPadding={16}>
                    <DropdownMenu.RadioGroup value={filters.sort} onValueChange={(value) => setFilters((current) => ({ ...current, sort: value as SortKey }))}>
                      {(Object.keys(SORT_LABELS) as SortKey[]).map((key) => <DropdownMenu.RadioItem key={key} value={key} className={styles.menuItem}>{SORT_LABELS[key]}</DropdownMenu.RadioItem>)}
                    </DropdownMenu.RadioGroup>
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
            </div>
          </div>

          {segment === "shelf" && tasteAccords && tasteAccords.length > 0 ? (
            <div className={styles.taste}>
              <AccordStrip accords={tasteAccords} className={styles.tasteStrip} />
              <Link href="/insights" className={styles.tasteLink}>Your taste</Link>
            </div>
          ) : null}

          {base.length === 0 && !filtered ? (
            segment === "shelf" ? (
              filters.finished
                ? <AtelierEmpty title="Nothing finished yet">Bottles you mark finished or sold appear here with their history.</AtelierEmpty>
                : <AtelierEmpty title="Your shelf starts here" action={<Button variant="outline" onClick={() => setAddOpen(true)}>Add fragrance</Button>}>Add a bottle, decant or sample and ScentIQ can start planning around it.</AtelierEmpty>
            ) : (
              <AtelierEmpty title="Nothing on your wishlist" action={<Link className="at-link" href="/discover">Find something in Discover</Link>}>Save fragrances you want to try and they collect here.</AtelierEmpty>
            )
          ) : visible.length === 0 ? (
            <AtelierEmpty title="Nothing matches" action={<Button variant="text" onClick={clearFilters}>Clear filters</Button>}>Try fewer filters or another search.</AtelierEmpty>
          ) : (
            <motion.ul layout className={styles.grid} aria-label={segment === "shelf" ? "Your shelf" : "Your wishlist"}>
              <AnimatePresence initial={false} mode="popLayout">
                {visible.map((item) => (
                  <motion.li key={item.id} layout initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.96 }} transition={motionTokens.quick}>
                    <FragranceCard
                      fragrance={plateFragrance(item.fragrance)}
                      accord={accordFor(item.fragrance)}
                      href={`/collection/${item.fragrance.id}`}
                      layoutId={`plate-${item.fragrance.id}`}
                      status={segment === "wishlist" ? "Wishlist" : statusLine(item)}
                      actions={actionsFor(item)}
                    />
                  </motion.li>
                ))}
              </AnimatePresence>
            </motion.ul>
          )}
        </>
      ) : saved === null ? (
        <AtelierEmpty title="Your blends did not load">Saved blends are unavailable right now. Your shelf is unaffected; try again shortly.</AtelierEmpty>
      ) : (
        <div className={styles.blends}>
          <ul className={styles.grid} aria-label="Your blends">
            <li>
              <Link href="/layering" className={styles.newBlend}>
                <span className={styles.newBlendTile} aria-hidden="true"><Plus /></span>
                <span className="at-card-title">New blend</span>
              </Link>
            </li>
            {saved.map((stack) => <li key={stack.id}><BlendVial stack={stack} /></li>)}
          </ul>
          {saved.length === 0 ? <AtelierEmpty title="No blends yet" action={<Button asChild variant="outline"><Link href="/layering">Start a blend</Link></Button>}>Pour two or three bottles together in Blend and save the ones you like.</AtelierEmpty> : null}
        </div>
      )}

      <AddFragranceDialog variant="sheet" open={addOpen} onOpenChange={setAddOpen} catalog={catalog} ownedFragranceIds={items.map((item) => item.fragrance.id)} />
      {wearItem ? <WearLogSheet itemId={wearItem.id} fragranceName={wearItem.fragrance.name} open onOpenChange={(open) => { if (!open) setWearItem(null); }} /> : null}
      <Sheet
        open={filtersOpen}
        onOpenChange={setFiltersOpen}
        title="Filters"
        footer={<div className={styles.sheetActions}><Button onClick={() => { setFilters((current) => ({ ...current, formats: draftFormats })); setFiltersOpen(false); }}>Apply</Button><Button variant="text" onClick={() => setDraftFormats([])}>Clear</Button></div>}
      >
        <fieldset className={styles.group}>
          <legend className="at-label">Format</legend>
          <div className={styles.chips}>
            {FORMATS.map(([value, label]) => <Chip key={value} variant="choice" pressed={draftFormats.includes(value)} onClick={() => setDraftFormats((current) => current.includes(value) ? current.filter((format) => format !== value) : [...current, value])}>{label}</Chip>)}
          </div>
        </fieldset>
      </Sheet>
    </div>
  );
}

export function CollectionSkeleton() {
  return (
    <div className="at-page" aria-busy="true">
      <span className="sr-only" role="status">Loading your collection</span>
      <span className="at-skeleton" style={{ width: 220, height: 48, marginBottom: 24 }} />
      <div className={styles.grid}>
        {Array.from({ length: 10 }, (_, index) => (
          <div key={index} aria-hidden="true" className={cn(styles.skeletonCard)}>
            <span className="at-skeleton" style={{ aspectRatio: "4 / 5" }} />
            <span className="at-skeleton" style={{ width: "70%", height: 14, marginTop: 10 }} />
          </div>
        ))}
      </div>
    </div>
  );
}
