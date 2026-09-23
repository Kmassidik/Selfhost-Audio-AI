import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * The tag vocabulary, in one place. The create page renders it as chips and the
 * jobs API validates against it, so a tag the page offers is a tag the API
 * accepts, and nothing else gets in.
 *
 * A tag is not decoration here: it picks the cover's colour and fills the
 * library's Categories list, which is why the list is fixed rather than free.
 */
export type TagGroups = Record<string, string[]>;

let cached: { groups: TagGroups; max_per_song: number } | null = null;

function vocabulary() {
	if (cached) return cached;
	// process.cwd() is the app root in the container; a path relative to this
	// module breaks once the server is bundled (learned with the catalogue)
	const file = join(process.cwd(), 'tags.json');
	const parsed = JSON.parse(readFileSync(file, 'utf8')) as { groups: TagGroups; max_per_song: number };
	cached = { groups: parsed.groups, max_per_song: parsed.max_per_song ?? 4 };
	return cached;
}

export function tag_groups(): TagGroups {
	return vocabulary().groups;
}

export function max_tags(): number {
	return vocabulary().max_per_song;
}

/** the canonical spelling of a tag, or null when it is not in the vocabulary */
export function canonical_tag(input: string): string | null {
	const wanted = input.trim().replace(/\s+/g, ' ').toLowerCase();
	for (const group of Object.values(tag_groups())) {
		for (const tag of group) {
			if (tag.toLowerCase() === wanted) return tag;
		}
	}
	return null;
}

export type TagCheck = { tags: string[]; errors: string[] };

/**
 * The rules, applied identically wherever they are needed: at most four tags,
 * each one from the vocabulary, each 3-24 characters, no commas (they separate
 * tags), no control characters, and no two spellings of the same tag.
 */
export function validate_tags(input: unknown): TagCheck {
	const errors: string[] = [];
	const raw = Array.isArray(input) ? input : typeof input === 'string' ? input.split(',') : [];
	const tags: string[] = [];

	if (raw.length > max_tags()) errors.push(`at most ${max_tags()} tags`);

	for (const item of raw) {
		const text = String(item ?? '').trim();
		if (!text) continue;
		if (text.length < 3 || text.length > 24) {
			errors.push(`"${text}" is not 3-24 characters`);
			continue;
		}
		if (/[,\u0000-\u001f]/.test(text)) {
			errors.push(`"${text}" has a comma or a control character`);
			continue;
		}
		const canonical = canonical_tag(text);
		if (!canonical) {
			errors.push(`"${text}" is not one of this box's categories`);
			continue;
		}
		if (tags.includes(canonical)) continue;
		tags.push(canonical);
	}

	return { tags, errors };
}
