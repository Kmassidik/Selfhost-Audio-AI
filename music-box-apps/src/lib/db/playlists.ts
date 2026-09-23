import { randomUUID } from 'node:crypto';
import type { Sql } from './index.js';
import type { SongRow } from './library.js';
import { ensure_listener } from './listeners.js';

/**
 * Playlists belong to a listener — an anonymous one is a listener like any
 * other, so grouping songs needs no account. A playlist also carries a share
 * id, so one can be handed to someone else as a link.
 */
export type Playlist = {
	id: number;
	name: string;
	share_id: string;
	songs: number;
	seconds: number;
};

export async function list_playlists(sql: Sql, listener: string): Promise<Playlist[]> {
	if (!listener) return [];
	return sql<Playlist[]>`
		SELECT p.id, p.name, p.share_id,
		       COUNT(pi.song_id)::int AS songs,
		       COALESCE(SUM(s.seconds), 0)::float AS seconds
		FROM playlists p
		LEFT JOIN playlist_items pi ON pi.playlist_id = p.id
		LEFT JOIN songs s ON s.id = pi.song_id
		WHERE p.listener_id = ${listener}
		GROUP BY p.id
		ORDER BY p.created_at DESC`;
}

export async function create_playlist(sql: Sql, listener: string, name: string): Promise<Playlist> {
	await ensure_listener(sql, listener);
	const [row] = await sql<Playlist[]>`
		INSERT INTO playlists (listener_id, name, created_at, cover_seed, share_id)
		VALUES (${listener}, ${name.slice(0, 80) || 'Playlist'},
		        to_char(now(), 'YYYY-MM-DD"T"HH24:MI:SS'), ${randomUUID().slice(0, 8)}, ${randomUUID()})
		RETURNING id, name, share_id, 0::int AS songs, 0::float AS seconds`;
	return row;
}

/** is this playlist this listener's? every write asks first, so a wrong id is a 404 */
export async function owns(sql: Sql, listener: string, id: number): Promise<boolean> {
	const rows = await sql`SELECT 1 FROM playlists WHERE id = ${id} AND listener_id = ${listener}`;
	return rows.length > 0;
}

export async function rename_playlist(sql: Sql, listener: string, id: number, name: string): Promise<boolean> {
	const rows = await sql`UPDATE playlists SET name = ${name.slice(0, 80)}
	          WHERE id = ${id} AND listener_id = ${listener} RETURNING id`;
	return rows.length > 0;
}

export async function delete_playlist(sql: Sql, listener: string, id: number): Promise<boolean> {
	const rows = await sql`DELETE FROM playlists WHERE id = ${id} AND listener_id = ${listener} RETURNING id`;
	if (rows.length) {
		await sql`DELETE FROM playlist_items WHERE playlist_id = ${id}`;
	}
	return rows.length > 0;
}

export async function add_song(sql: Sql, listener: string, id: number, song_id: string): Promise<void> {
	// position is the next free slot; the same song twice is ignored
	await sql`
		INSERT INTO playlist_items (playlist_id, song_id, position)
		SELECT p.id, ${song_id}, COALESCE(MAX(pi.position), -1) + 1
		FROM playlists p
		LEFT JOIN playlist_items pi ON pi.playlist_id = p.id
		WHERE p.id = ${id} AND p.listener_id = ${listener}
		  AND EXISTS (SELECT 1 FROM songs WHERE id = ${song_id} AND visible = TRUE)
		GROUP BY p.id
		ON CONFLICT DO NOTHING`;
}

export async function remove_song(sql: Sql, listener: string, id: number, song_id: string): Promise<void> {
	await sql`
		DELETE FROM playlist_items
		WHERE playlist_id IN (SELECT id FROM playlists WHERE id = ${id} AND listener_id = ${listener})
		  AND song_id = ${song_id}`;
}

/** one playlist's songs, in the order they were put in */
export async function playlist_songs(
	sql: Sql,
	where: { id?: number; share_id?: string; listener?: string }
): Promise<{ playlist: Playlist | null; items: SongRow[]; total: number }> {
	const [playlist] = await sql<Playlist[]>`
		SELECT p.id, p.name, p.share_id, COUNT(pi.song_id)::int AS songs,
		       COALESCE(SUM(s.seconds), 0)::float AS seconds
		FROM playlists p
		LEFT JOIN playlist_items pi ON pi.playlist_id = p.id
		LEFT JOIN songs s ON s.id = pi.song_id
		WHERE ${where.share_id ? sql`p.share_id = ${where.share_id}` : sql`p.id = ${where.id ?? -1}`}
		GROUP BY p.id`;
	if (!playlist) return { playlist: null, items: [], total: 0 };

	const listener = where.listener ?? '';
	const items = await sql<SongRow[]>`
		SELECT s.id, s.title, s.model, s.seed, s.style, s.lyrics, s.seconds, s.created_at,
		       s.source, s.cover_v, s.has_mp3, s.has_video, s.formats,
		       COALESCE(ARRAY_REMOVE(ARRAY_AGG(DISTINCT t.tag), NULL), '{}') AS tags,
		       (CASE WHEN ${listener} = '' THEN FALSE ELSE s.id IN
		           (SELECT song_id FROM likes WHERE listener_id = ${listener}) END) AS liked
		FROM playlist_items pi
		JOIN songs s ON s.id = pi.song_id AND s.visible = TRUE
		LEFT JOIN tags t ON t.song_id = s.id
		WHERE pi.playlist_id = ${playlist.id}
		GROUP BY s.id, pi.position
		ORDER BY pi.position ASC`;
	return { playlist, items, total: items.length };
}
