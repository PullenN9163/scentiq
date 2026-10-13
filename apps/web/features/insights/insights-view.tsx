"use client";

import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { ExperienceBackdrop } from "@/components/shared/experience";
import "./insights.css";

import Link from "next/link";

import { PageHeader } from "@/components/shared/page-header";
import { EmptyState } from "@/components/shared/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { CollectionInsights } from "@/types/api";

/**
 * Insights computed from the caller's persisted collection and wear history.
 *
 * Custom fragrances usually carry no accord, season or occasion data, so every
 * breakdown states how many items it could not classify rather than implying it
 * covers the whole collection.
 */
export function InsightsView({ insights }: { insights: CollectionInsights }) {
  if (insights.total_items === 0) {
    return (
      <section className="page experience-page insights-experience">
        <ExperienceBackdrop tone="insights" />
      <PageHeader
          eyebrow="Collection intelligence"
          title="Insights"
          description="Patterns in what you own and reach for."
        />
        <EmptyState
          title="Nothing to analyse yet"
          description="Add a few fragrances and log some wears, and your patterns will appear here."
          action={
            <Button asChild variant="secondary">
              <Link href="/collection">Go to collection</Link>
            </Button>
          }
        />
      </section>
    );
  }

  const metrics: [string, string | number][] = [
    ["In collection", insights.total_items],
    ["Owned", insights.owned_items],
    [
      "Invested",
      insights.total_purchase_value === null
        ? "Not recorded"
        : insights.total_purchase_value,
    ],
    ["Total wears", insights.total_wears],
    ["Wears (30 days)", insights.wears_last_30_days],
    [
      "Average rating",
      insights.average_rating === null
        ? "Not rated"
        : `${insights.average_rating} / 5`,
    ],
  ];

  const classifiedItems = insights.total_items - insights.unclassified_items;

  return (
    <section className="page experience-page insights-experience">
      <ExperienceBackdrop tone="insights" />
      <PageHeader
        eyebrow="Collection intelligence"
        title="Insights"
        description="Patterns in what you own, reach for, and might use more intentionally."
      />

      <div className="metric-grid insight-metrics">
        {metrics.map(([label, value]) => (
          <Card key={label}>
            <CardContent>
              <span>{label}</span>
              <strong
                className={typeof value === "number" ? "metric-number" : ""}
              >
                {value}
              </strong>
            </CardContent>
          </Card>
        ))}
      </div>

      {insights.priced_items < insights.total_items ? (
        <p className="data-note">
          {insights.priced_items} of {insights.total_items} items have a
          recorded price, so the invested total covers only those.
        </p>
      ) : null}

      <div className="insight-charts insight-stage">
        <Card>
          <CardContent>
            <p className="eyebrow">Your scent fingerprint</p>
            <h2 className="serif">Accord distribution</h2>
            <ScentFingerprint accords={insights.accords} />
            {insights.unclassified_items > 0 ? (
              <p className="data-note">
                Based on {classifiedItems} of {insights.total_items} items.{" "}
                {insights.unclassified_items}{" "}
                {insights.unclassified_items === 1 ? "item has" : "items have"}{" "}
                no classification data — custom entries normally do not.
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <p className="eyebrow">Rotation</p>
            <h2 className="serif">Most worn</h2>
            {insights.most_worn.length === 0 ? (
              <p className="muted">No wears logged yet.</p>
            ) : (
              <div className="note-bars">
                {insights.most_worn.map((entry) => (
                  <div key={entry.collection_item_id}>
                    <span>{entry.fragrance_name}</span>
                    <Progress
                      value={Math.round(
                        (entry.wear_count / insights.most_worn[0].wear_count) *
                          100,
                      )}
                      label={`${entry.fragrance_name} wear count`}
                    />
                    <strong>{entry.wear_count}</strong>
                  </div>
                ))}
              </div>
            )}
            <p className="muted">
              {insights.distinct_fragrances_worn} of {insights.total_items} have
              been worn.
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-2 insight-notes">
        <Card>
          <CardContent>
            <p className="eyebrow">Ownership mix</p>
            <h2 className="serif">Formats on the shelf</h2>
            {insights.ownership_types.map((slice) => (
              <p key={slice.label}>
                <strong>{slice.label}</strong> · {slice.count}
              </p>
            ))}
            {insights.custom_items > 0 ? (
              <p className="data-note">
                {insights.custom_items}{" "}
                {insights.custom_items === 1 ? "item is" : "items are"} your own
                custom entries.
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardContent>
            <p className="eyebrow">Status</p>
            <h2 className="serif">Where things stand</h2>
            <p>
              <strong>Owned</strong> · {insights.owned_items}
            </p>
            <p>
              <strong>Wishlist</strong> · {insights.wishlist_items}
            </p>
            <p>
              <strong>Finished or sold</strong> · {insights.retired_items}
            </p>
            <p className="data-note">
              Retired items keep their wear history, so past totals stay
              accurate.
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-3 insight-notes">
        <Card>
          <CardContent>
            <p className="eyebrow">Rotation opportunities</p>
            <h2 className="serif">A little neglected</h2>
            {(insights.neglected ?? []).length ? (
              insights.neglected?.map((entry) => (
                <div key={entry.collection_item_id}>
                  <Link href={`/collection/${entry.fragrance_id}`}>
                    {entry.fragrance_name}
                  </Link>
                  <p>
                    {entry.wear_count} wears ·{" "}
                    {entry.last_worn_at
                      ? `Last worn ${new Date(entry.last_worn_at).toLocaleDateString()}`
                      : "Never logged"}
                  </p>
                </div>
              ))
            ) : (
              <p>No neglected fragrances in your current owned rotation.</p>
            )}
            <p className="data-note">
              Owned fragrances with no logged wear in the last 30 days.
            </p>
            <details>
              <summary>Least worn</summary>
              {(insights.least_worn ?? []).map((entry) => (
                <p key={entry.collection_item_id}>
                  {entry.fragrance_name} · {entry.wear_count} wears
                </p>
              ))}
            </details>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <p className="eyebrow">Personal favorites</p>
            <h2 className="serif">Highest rated</h2>
            {(insights.highest_rated ?? []).length ? (
              insights.highest_rated?.map((entry) => (
                <p key={entry.collection_item_id}>
                  <Link href={`/collection/${entry.fragrance_id}`}>
                    {entry.fragrance_name}
                  </Link>{" "}
                  · {entry.user_rating} / 5
                </p>
              ))
            ) : (
              <p>Rate owned fragrances to see your favorites.</p>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <p className="eyebrow">Recorded value</p>
            <h2 className="serif">Cost per wear</h2>
            {(insights.cost_per_wear ?? []).length ? (
              insights.cost_per_wear?.map((entry) => (
                <div key={entry.collection_item_id}>
                  <Link href={`/collection/${entry.fragrance_id}`}>
                    {entry.fragrance_name}
                  </Link>
                  <p>
                    {entry.cost_per_wear} per wear · {entry.wear_count} logged
                  </p>
                </div>
              ))
            ) : (
              <p>Record purchase prices and a wear to see value per wear.</p>
            )}
            <p className="data-note">
              Recorded purchase price divided by logged wears. Unpriced or
              unworn bottles are excluded.
            </p>
          </CardContent>
        </Card>
      </div>
      <div className="grid grid-2 insight-notes">
        <Card>
          <CardContent>
            <p className="eyebrow">Recorded note structure</p>
            <h2 className="serif">Notes across your shelf</h2>
            {(insights.note_frequency ?? []).length ? (
              <div className="note-bars">
                {insights.note_frequency?.map((note) => (
                  <div key={`${note.stage}:${note.label}`}>
                    <span>
                      {note.label} · {note.stage}
                    </span>
                    <Progress
                      value={Math.round(note.share * 100)}
                      label={`${note.label} ${note.stage} representation`}
                    />
                    <strong>{note.count}</strong>
                  </div>
                ))}
              </div>
            ) : (
              <p>Not enough recorded note data yet.</p>
            )}
            <p className="data-note">
              Notes count each owned fragrance once per stage. Shares cover
              fragrances with recorded notes.
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent>
            <p className="eyebrow">Similar profiles</p>
            <h2 className="serif">Where your scents overlap</h2>
            {(insights.redundancy_pairs ?? []).length ? (
              insights.redundancy_pairs?.map((pair) => (
                <div key={`${pair.first_id}:${pair.second_id}`}>
                  <p>
                    <Link href={`/collection/${pair.first_id}`}>
                      {pair.first_name}
                    </Link>{" "}
                    +{" "}
                    <Link href={`/collection/${pair.second_id}`}>
                      {pair.second_name}
                    </Link>
                  </p>
                  <Progress
                    value={Math.round(pair.overlap * 100)}
                    label={`${pair.first_name} and ${pair.second_name} accord overlap`}
                  />
                  <p>
                    {Math.round(pair.overlap * 100)}% weighted accord overlap ·{" "}
                    {pair.shared_accords.join(", ")}
                  </p>
                </div>
              ))
            ) : (
              <p>
                No high-overlap pair is supported by the recorded accord data.
              </p>
            )}
            <p className="data-note">
              Similar accords suggest repeated profile coverage, not identical
              scent or performance. Comparisons cover up to 200 owned items.
            </p>
          </CardContent>
        </Card>
      </div>
      <Card className="coverage-card insight-coverage">
        <CardContent>
          <p className="eyebrow">Season coverage — source-backed</p>
          <h2 className="serif">Where your wardrobe is ready</h2>
          {insights.seasons.length === 0 ? (
            <p className="muted">Not enough source-backed season data yet.</p>
          ) : (
            <div className="coverage-grid">
              {insights.seasons.map((slice) => (
                <div key={slice.label}>
                  <div>
                    <strong>{slice.label}</strong>
                    <Badge>{slice.count}</Badge>
                  </div>
                  <Progress
                    value={Math.round(slice.share * 100)}
                    label={`${slice.label} coverage`}
                  />
                </div>
              ))}
            </div>
          )}
          {insights.season_coverage_score != null ? (
            <>
              <p>
                Season coverage quality:{" "}
                {Math.round(insights.season_coverage_score * 100)}%
              </p>
              <p className="data-note">
                {Math.round((insights.season_evidence_coverage ?? 0) * 100)}% of
                owned fragrances have season evidence. Quality averages the best
                recorded fit available for each of four seasons.
              </p>
              {(insights.season_gaps ?? []).length ? (
                <p>
                  Less supported seasons: {insights.season_gaps?.join(", ")}.
                  Explore your existing scents before considering a purchase.
                </p>
              ) : null}
            </>
          ) : null}
          <h3>Occasion behavior — based on your wear history</h3>
          {(insights.occasion_behavior ?? []).length ? (
            insights.occasion_behavior?.map((slice) => (
              <p key={slice.label}>
                {slice.label} · {slice.count} logged wears
              </p>
            ))
          ) : (
            <p>Not enough occasion history yet.</p>
          )}
          <p className="data-note">
            Season percentages show shares of recorded season classifications.
            A fragrance can have more than one classification.
          </p>
        </CardContent>
      </Card>
    </section>
  );
}

function ScentFingerprint({ accords }: { accords: CollectionInsights["accords"] }) {
  const [selected, setSelected] = useState(0);
  const reduced = useReducedMotion();
  const effectiveSelected = Math.min(selected, Math.max(0, accords.length - 1));
  const current = accords[effectiveSelected];
  if (!current) return <p className="muted">None of your fragrances carry accord data yet, so there is nothing to chart.</p>;
  const visible = accords.slice(0, 6);
  if (effectiveSelected >= 6) visible[5] = current;
  return <div className="fingerprint">
    <div className="fingerprint__visual">
      <div className="fingerprint__halo" aria-hidden="true" />
      <svg viewBox="0 0 360 360" aria-hidden="true" className="fingerprint__rings">
        {visible.map((accord, index) => {
          const radius = 156 - index * 16;
          const circumference = 2 * Math.PI * radius;
          const accordIndex = accords.indexOf(accord);
          return <g key={accord.label} data-accord={accord.label} data-selected={effectiveSelected === accordIndex} className={`fingerprint__ring fingerprint__ring--${accordIndex % 12}`}>
            <circle cx="180" cy="180" r={radius} fill="none" stroke="var(--border)" strokeWidth="7" opacity=".5" />
            <motion.circle cx="180" cy="180" r={radius} fill="none" stroke="var(--ring-color)" strokeWidth={effectiveSelected === accordIndex ? 10 : 7} strokeLinecap="round" transform="rotate(-90 180 180)" strokeDasharray={circumference} initial={reduced ? false : { strokeDashoffset: circumference }} animate={{ strokeDashoffset: circumference * (1 - Math.min(1, Math.max(0, accord.share))) }} transition={{ duration: reduced ? 0 : .7 }} opacity={effectiveSelected === accordIndex ? 1 : .55} />
          </g>;
        })}
      </svg>
      <div className="fingerprint__center" data-testid="selected-profile" aria-live="polite"><span className="eyebrow">Recorded share</span><strong>{Math.round(current.share * 100)}<small>%</small></strong><span>{current.label}</span><small>{current.count} {current.count === 1 ? "fragrance" : "fragrances"}</small></div>
    </div>
    <div className="fingerprint__legend">
      {accords.map((accord, index) => <button type="button" key={accord.label} aria-label={`Inspect ${accord.label} accord`} aria-pressed={effectiveSelected === index} onClick={() => setSelected(index)} className={`fingerprint__choice fingerprint__ring--${index % 12}`}><i aria-hidden="true" /><span>{accord.label}</span><strong>{Math.round(accord.share * 100)}%</strong></button>)}
      <p className="data-note">Share of the displayed recorded accord occurrences, not the percentage of bottles. Select an accord to explore your profile.</p>
    </div>
  </div>;
}
