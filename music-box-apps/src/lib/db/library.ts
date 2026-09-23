import type { Sql } from './index.js';

/**
 * The library's SQL — every reply a listener sees comes from here.
 * Two rules hold throughout: parameters only bind, never concatenate; every
 * list is paged, never whole.
 */

export type SongRow = {
	id: string;
	title: string;
	model: string;
	seed: string;
	style: string;
	lyrics: string;
	seconds: number;
	created_at: string;
	source: string;
	cover_v: number;
	has_mp3: boolean;
	has_video: boolean;
	formats: string[];
	tags: string[];
	liked: boolean;
};

const SORTS: Record<string, string> = {
	new: 's.created_at DESC, s.id DESC',
	old: 's.created_at ASC, s.id ASC',
	long: 's.seconds DESC',
	short: 's.seconds ASC',
	title: 's.title COLLATE "C" ASC',
	played: '(SELECT COUNT(*) FROM plays p WHERE p.song_id = s.id) DESC',
	liked: '(s.id IN (SELECT song_id FROM likes WHERE listener_id = $LIS)) DESC, s.created_at DESC'
};
export type SortKey = keyof typeof SORTS;

/** One order per seed: the deterministic md5 shuffle the old UI relied on */
function shuffle_order(seed: number): string {
	const s = Math.abs(Math.trunc(seed)) % 1_000_000_000;
	return `md5(${s}::text || s.id)`;
}

export type LibraryQuery = {
	q?: string;
	model?: string;
	tag?: string;
	ids?: string[];
	liked?: boolean;
	listener?: string;
	sort?: SortKey | 'random';
	seed?: number;
	offset?: number;
	limit?: number;
};

type RawSong = SongRow & { count?: number };

function shape_song(r: RawSong): SongRow {
	return {
		id: r.id,
		title: r.title,
		model: r.model,
		seed: r.seed,
		style: r.style,
		lyrics: r.lyrics,
		seconds: r.seconds,
		created_at: r.created_at,
		source: r.source,
		creator_id: r.creator_id ?? '',
		sample_rate: r.sample_rate ?? 0,
		channels: r.channels ?? 0,
		cover_v: r.cover_v,
		has_mp3: r.has_mp3,
		has_video: r.has_video,
		formats: r.formats ?? ['mp3'],
		tags: r.tags ?? [],
		liked: Boolean(r.liked)
	};
}

/**
 * Builds the WHERE clause and its arguments together, so a condition can
 * never drift from the value it binds. `listener` marks the one column the
 * liked flag and the liked sort read.
 */
function build_filter(params: LibraryQuery): { where: string; args: unknown[] } {
	const conditions = ['s.visible = TRUE'];
	const args: unknown[] = [];

	if (params.q) {
		args.push(params.q);
		conditions.push(`s.search @@ plainto_tsquery('simple', $${args.length})`);
	}
	if (params.model) {
		args.push(params.model);
		conditions.push(`s.model = $${args.length}`);
	}
	if (params.tag) {
		args.push(params.tag);
		conditions.push(`s.id IN (SELECT song_id FROM tags WHERE tag = $${args.length})`);
	}
	if (params.ids?.length) {
		args.push(params.ids);
		conditions.push(`s.id = ANY($${args.length}::text[])`);
	}
	if (params.liked) {
		args.push(params.listener ?? '');
		conditions.push(`s.id IN (SELECT song_id FROM likes WHERE listener_id = $${args.length})`);
	}
	return { where: conditions.join(' AND '), args };
}

/** the liked sort binds the listener's id like every other value, never inlines it */
function order_for(params: LibraryQuery, listener_param: number): string {
	if (params.sort === 'random') return shuffle_order(params.seed ?? 0);
	const order = SORTS[params.sort ?? 'new'] ?? SORTS.new;
	return order.replaceAll('$LIS', `$${listener_param}`);
}

/**
 * One page of the library, plus the total so a page can show progress.
 */
export async function page_library(
	sql: Sql,
	params: LibraryQuery
): Promise<{ items: SongRow[]; total: number; offset: number; limit: number }> {
	const used = Math.max(1, Math.min(params.limit ?? 50, 200));
	const offset = Math.max(0, params.offset ?? 0);
	const { where, args } = build_filter(params);
	const listener = params.listener ?? '';
	const listener_param = args.length + 1;

	const rows = await sql.unsafe<RawSong[]>(
		`SELECT s.id, s.title, s.model, s.seed, s.style, s.lyrics, s.seconds, s.created_at,
		        s.creator_id, s.source, s.cover_v, s.has_mp3, s.has_video, s.formats,
		        COALESCE(ARRAY_REMOVE(ARRAY_AGG(DISTINCT t.tag), NULL), '{}') AS tags,
		        (CASE WHEN $${listener_param} = '' THEN FALSE ELSE s.id IN
		            (SELECT song_id FROM likes WHERE listener_id = $${listener_param}) END) AS liked,
		        (COUNT(*) OVER ()) AS count
		 FROM songs s
		 LEFT JOIN tags t ON t.song_id = s.id
		 WHERE ${where}
		 GROUP BY s.id
		 ORDER BY ${order_for(params, listener_param)}
		 LIMIT $${listener_param + 1} OFFSET $${listener_param + 2}`,
		[...args, listener, used, offset]
	);

	return { items: rows.map(shape_song), total: await total_for(sql, params, rows), offset, limit: used };
}

/** the window count is free when rows came back; otherwise ask again */
async function total_for(sql: Sql, params: LibraryQuery, rows: RawSong[]): Promise<number> {
	if (rows.length > 0) return Number(rows[0].count);
	const { where, args } = build_filter(params);
	const [r] = await sql.unsafe<[{ n: number }]>(
		`SELECT COUNT(*)::int AS n FROM songs s WHERE ${where}`,
		args
	);
	return r?.n ?? 0;
}

/** One song in full, with its words — the details drawer asks for this. */
export async function get_song(sql: Sql, id: string, listener = ''): Promise<SongRow | null> {
	const rows = await sql<RawSong[]>`
		SELECT s.id, s.title, s.model, s.seed, s.style, s.lyrics, s.seconds, s.created_at,
		       s.sample_rate, s.channels, s.creator_id,
		       s.source, s.cover_v, s.has_mp3, s.has_video, s.formats,
		       COALESCE(ARRAY_REMOVE(ARRAY_AGG(DISTINCT t.tag), NULL), '{}') AS tags,
		       (CASE WHEN ${listener} = '' THEN FALSE ELSE s.id IN
		           (SELECT song_id FROM likes WHERE listener_id = ${listener}) END) AS liked
		FROM songs s LEFT JOIN tags t ON t.song_id = s.id
		WHERE s.id = ${id} AND s.visible = TRUE
		GROUP BY s.id`;
	return rows[0] ? shape_song(rows[0]) : null;
}

/** What was played last, newest first, one row per song. */
export async function recently_played(sql: Sql, limit = 6, listener = ''): Promise<SongRow[]> {
	const rows = await sql<RawSong[]>`
		SELECT s.id, s.title, s.model, s.seed, s.style, s.lyrics, s.seconds, s.created_at,
		       s.creator_id, s.source, s.cover_v, s.has_mp3, s.has_video, s.formats,
		       COALESCE(ARRAY_REMOVE(ARRAY_AGG(DISTINCT t.tag), NULL), '{}') AS tags,
		       (CASE WHEN ${listener} = '' THEN FALSE ELSE s.id IN
		           (SELECT song_id FROM likes WHERE listener_id = ${listener}) END) AS liked
		FROM songs s
		LEFT JOIN tags t ON t.song_id = s.id
		JOIN plays p ON p.song_id = s.id
		WHERE s.visible = TRUE
		GROUP BY s.id
		ORDER BY MAX(p.played_at) DESC
		LIMIT ${limit}`;
	return rows.map(shape_song);
}

export type Counts = {
	songs: number;
	seconds: number;
	liked: number;
	plays: number;
	models: { model: string; songs: number }[];
};

/** The counts the sidebar shows, over the same slice of the library. */
export async function counts(sql: Sql, listener = ''): Promise<Counts> {
	const [[songsRow], [likedRow], [playsRow], modelRows] = await Promise.all([
		sql<[{ songs: number; seconds: number }]>`
			SELECT COUNT(*)::int AS songs, COALESCE(SUM(seconds), 0)::float AS seconds
			FROM songs WHERE visible = TRUE`,
		sql<[{ n: number }]>`
			SELECT COUNT(*)::int AS n FROM likes l JOIN songs s ON s.id = l.song_id
			WHERE s.visible = TRUE AND l.listener_id = ${listener}`,
		sql<[{ n: number }]>`SELECT COUNT(*)::int AS n FROM plays`,
		sql<{ model: string; songs: number }[]>`
			SELECT model, COUNT(*)::int AS songs FROM songs
			WHERE visible = TRUE GROUP BY model ORDER BY songs DESC`
	]);
	return {
		songs: songsRow.songs,
		seconds: songsRow.seconds,
		liked: likedRow.n,
		plays: playsRow.n,
		models: modelRows.map((m) => ({ model: m.model, songs: m.songs }))
	};
}

/** Every category with enough songs to fill a filter chip, biggest first. */
export async function top_tags(
	sql: Sql,
	minimum = 2,
	limit = 24
): Promise<{ tag: string; songs: number }[]> {
	return sql<{ tag: string; songs: number }[]>`
		SELECT t.tag, COUNT(DISTINCT t.song_id)::int AS songs
		FROM tags t JOIN songs s ON s.id = t.song_id AND s.visible = TRUE
		GROUP BY t.tag HAVING COUNT(DISTINCT t.song_id) >= ${minimum}
		ORDER BY songs DESC, t.tag ASC LIMIT ${limit}`;
}
