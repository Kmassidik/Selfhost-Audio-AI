import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import type { Sql } from '$lib/db/index.js';

/**
 * The catalogue: one JSON file per model under catalog/. A new model on an
 * existing engine is a file, not code. This module is the only reader of
 * those files, and it answers the shapes the create page already expects.
 */
type ModelSpec = {
	id: string;
	enabled: boolean;
	name: string;
	kind: string;
	fields: string[];
	limits: Record<string, number>;
	cards: number;
	rate: number;
	traits: Record<string, unknown>;
	outcome: { title?: string; blurb?: string; icon?: string; order?: number };
};

let cache: ModelSpec[] | null = null;

function catalog_dir(): string {
	// the container's working directory is the app root; a path relative to
	// this module breaks once the server is bundled (measured on the box)
	return join(process.cwd(), 'catalog');
}

/** every enabled model, read once per process */
export function models(): ModelSpec[] {
	if (cache) return cache;
	const dir = catalog_dir();
	cache = readdirSync(dir)
		.filter((f) => f.endsWith('.json'))
		.map((f) => JSON.parse(readFileSync(join(dir, f), 'utf8')) as ModelSpec)
		.filter((m) => m.enabled !== false);
	return cache;
}

export function get_model(id: string): ModelSpec | undefined {
	return models().find((m) => m.id === id);
}

/**
 * Seconds of work per second of music, from this box's own finished jobs — a
 * declared rate is a guess until three real runs replace it.
 */
export async function measured_rate(
	sql: Sql,
	model: string,
	declared: number
): Promise<[number, 'measured' | 'estimated']> {
	const rows = await sql<{ wall_s: number; seconds: number }[]>`
		SELECT j.wall_s, s.seconds
		FROM jobs j JOIN songs s ON s.id = j.song_id
		WHERE j.model = ${model} AND j.status = 'done' AND j.wall_s > 0 AND s.seconds > 0
		ORDER BY j.id DESC LIMIT 8`;
	if (rows.length < 3) return [declared, 'estimated'];
	const rates = rows.map((r) => r.wall_s / r.seconds).sort((a, b) => a - b);
	const median = rates[Math.floor(rates.length / 2)] ?? declared;
	return [Math.round(median * 100) / 100, 'measured'];
}

/**
 * How long this model sings one word, measured here. Neither singing model
 * obeys a length, so the honest prediction is made from the words.
 */
export async function seconds_per_word(sql: Sql, model: string): Promise<number> {
	const rows = await sql<{ seconds: number; lyrics: string }[]>`
		SELECT seconds, lyrics FROM songs
		WHERE model = ${model} AND seconds > 0 AND lyrics <> ''
		ORDER BY created_at DESC LIMIT 12`;
	const rates: number[] = [];
	for (const r of rows) {
		const words = r.lyrics.replace(/\[[^\]]*\]/g, ' ').split(/\s+/).filter(Boolean).length;
		if (words >= 20) rates.push(r.seconds / words);
	}
	if (rates.length < 3) return 0;
	rates.sort((a, b) => a - b);
	return Math.round((rates[Math.floor(rates.length / 2)] ?? 0) * 100) / 100;
}

/** The choices a person picks between, with this box's own speed figures. */
export async function outcomes(sql: Sql, music_only = true): Promise<Record<string, unknown>[]> {
	const out = [];
	for (const spec of models()) {
		if (music_only && spec.kind !== 'sing') continue;
		const [rate, source] = await measured_rate(sql, spec.id, spec.rate ?? 1);
		out.push({
			id: spec.id,
			name: spec.name,
			traits: spec.traits ?? {},
			title: spec.outcome?.title ?? spec.name,
			blurb: spec.outcome?.blurb ?? '',
			icon: spec.outcome?.icon ?? '',
			order: spec.outcome?.order ?? 99,
			fields: spec.fields ?? [],
			cards: spec.cards ?? 1,
			limits: spec.limits ?? {},
			rate,
			rate_source: source,
			seconds_per_word: await seconds_per_word(sql, spec.id)
		});
	}
	return out.sort((a, b) => Number(a.order) - Number(b.order));
}
