import { counts, page_library, recently_played } from '$lib/db/library.js';
import { playlist_songs } from '$lib/db/playlists.js';
import type { SortKey } from '$lib/db/library.js';

/**
 * The listen page, in four shapes: a playlist, the home shelves, a filtered
 * library, and a search. Likes are always the visitor's own.
 */
const SMALL_LIBRARY = 12;

export const load = async ({ url, locals }) => {
	const params = url.searchParams;
	const listener = locals.listener;
	const q = params.get('q') ?? '';
	const tag = params.get('tag') ?? '';
	const playlist_id = Number(params.get('playlist') ?? 0);
	const view = params.get('view') ?? (q || tag ? 'all' : 'home');
	const sort = (params.get('sort') as SortKey | null) ?? 'new';
	const sql = locals.sql;

	if (playlist_id) {
		const { playlist, items } = await playlist_songs(sql, { id: playlist_id, listener });
		return {
			shape: 'grid',
			title: playlist?.name ?? 'Playlist',
			items,
			total: items.length,
			shelves: [],
			sort,
			q,
			tag,
			view: 'playlist',
			playlist
		};
	}

	if (view === 'home' && !q && !tag) {
		const total = (await counts(sql)).songs;
		const recent = await recently_played(sql, 6, listener);
		const newest = (await page_library(sql, { sort: 'new', limit: 1, listener })).items;
		const feature = newest[0] ?? null;

		if (total < SMALL_LIBRARY) {
			const all = await page_library(sql, { sort: 'new', limit: 100, listener });
			return { shape: 'small', title: 'All songs', items: all.items, total, shelves: [], sort, q, tag, view };
		}

		const rows = await page_library(sql, { sort: 'new', limit: 12, listener });
		const shelves = [
			...(recent.length ? [{ title: 'Recently played', items: recent }] : []),
			{ title: rows.total > 12 ? 'Latest' : 'All songs', items: rows.items }
		];
		return { shape: 'home', title: 'All songs', items: rows.items, total, shelves, feature, sort, q, tag, view };
	}

	const page = await page_library(sql, { q, tag, sort, liked: view === 'liked', listener, limit: 60 });
	const title = q ? `“${q}”` : tag ? tag : view === 'liked' ? 'Liked' : 'All songs';
	return { shape: 'grid', title, items: page.items, total: page.total, shelves: [], sort, q, tag, view };
};
