/**
 * import.ts — carries the old library out of `data/studio/app.db` (SQLite)
 * into the new postgres database.
 *
 * Point of discipline: this script ALSO restores from a backup the same way
 * it imports from the old system. It is the one mover of facts, so it is the
 * one place a fact can be verified moved.
 *
 * Default is a dry run: it reads and reports. `--apply` writes.
 *
 *   DATABASE_URL=... bun run ./import/import.ts [--apply] [--db path/to/app.db]
 */

import { Database } from 'bun:sqlite';
import { basename } from 'node:path';
import postgres from 'postgres';

const APPLY = process.argv.includes('--apply');
const dbPath =
	process.argv[process.argv.indexOf('--db') + 1] ?? '/root/Desktop/selfhostaudioai/data/studio/app.db';
const url = process.env.DATABASE_URL ?? 'postgres://music:music@127.0.0.1:5432/musicbox';

const old = new Database(dbPath, { readonly: true, create: false });
const sql = postgres(url, { max: 2 });

/** rows of a name table */
type Row = Record<string, unknown>;
const rows = (q: string): Row[] => old.prepare(q).all() as Row[];

/** every song id the old library imported — the set a job may point at */
const imported_song_ids = new Set();

/** a job's song link, nulled when the song is not part of this import */
async function handled(song_id: unknown): Promise<string | null> {
	if (typeof song_id !== 'string' || !imported_song_ids.has(song_id)) return null;
	return song_id;
}
// ── the one listener under which every imported song's history lands ──────
const MIGRATED_ID = 'migrated';

function nowIso(): string {
	return new Date().toISOString().slice(0, 19);
}

async function main() {
	const songs = rows(`SELECT * FROM songs WHERE visible=1`);
	const likes = rows(`SELECT song_id, created_at FROM likes`);
	const plays = rows(`SELECT song_id, played_at, seconds_played FROM plays`);
	const tags = rows(`SELECT song_id, tag FROM song_tags`);
	const jobs = rows(`SELECT * FROM jobs`);

	console.log(`source: ${basename(dbPath)}`);
	console.log(
		JSON.stringify(
			{ songs: songs.length, likes: likes.length, plays: plays.length, tags: tags.length, jobs: jobs.length },
			null,
			2
		)
	);
	if (!APPLY) {
		console.log('dry run — pass --apply to write');
		return;
	}

	await sql.begin(async (tx) => {
		await tx`INSERT INTO listeners (id, kind, label, created_at)
		          VALUES (${MIGRATED_ID}, 'anonymous', 'before the rebuild', ${nowIso()})
		          ON CONFLICT (id) DO NOTHING`;

		for (const s of songs) {
			const formats = ['mp3'];
			if (s.video_path) formats.push('mp4');
			await tx`
				INSERT INTO songs
				  (id, title, model, seed, style, lyrics, seconds, sample_rate, channels,
				   created_at, source, creator_id, visible, has_mp3, has_video, cover_v, formats, search)
				VALUES (${s.id}, ${s.title}, ${s.model}, ${s.seed}, ${s.style}, ${s.lyrics},
				        ${s.seconds}, ${s.sample_rate}, ${s.channels}, ${s.created_at}, ${s.source},
				        ${MIGRATED_ID}, TRUE, ${Boolean(s.mp3_path)}, ${Boolean(s.video_path)},
				        ${Math.floor(Date.parse(String(s.created_at) || nowIso()) / 1000) | 0},
				        ${formats},
				        lower(${`${s.title} ${s.style} ${s.lyrics} ${s.model}`}))
				ON CONFLICT (id) DO NOTHING`;
			imported_song_ids.add(String(s.id));
		}

		for (const t of tags) {
			await tx`INSERT INTO tags (song_id, tag) VALUES (${t.song_id}, ${t.tag})
			          ON CONFLICT DO NOTHING`;
		}

		for (const l of likes) {
			// global likes in the old system belong to one house; they import on
			// the single migrated listener and can be re-liked per person after.
			await tx`INSERT INTO likes (listener_id, song_id, created_at)
			          VALUES (${MIGRATED_ID}, ${l.song_id}, ${l.created_at})
			          ON CONFLICT DO NOTHING`;
		}

		await tx`DELETE FROM plays WHERE 1=1`;
		for (const p of plays) {
			await tx`INSERT INTO plays (song_id, listener_id, played_at, seconds_played)
			          VALUES (${p.song_id}, ${MIGRATED_ID}, ${p.played_at}, ${p.seconds_played ?? 0})`;
		}

		for (const j of jobs) {
			// a job may point at a song that was deleted in the old library; its
			// song link is history, not a fact to enforce — insert with null
			const sk = await handled(j.song_id);
			await tx`
				INSERT INTO jobs (song_id, model, title, params, status, error, creator_id, created_at, started_at, finished_at, wall_s)
				VALUES (${sk}, ${j.model}, ${j.title}, ${String(j.params)}, ${j.status},
				        ${j.error}, ${MIGRATED_ID}, ${j.created_at}, ${j.started_at}, ${j.finished_at}, ${j.wall_s})`;
		}
	});

	const [counts] = (await sql`
		SELECT
		  (SELECT COUNT(*) FROM songs) AS songs,
		  (SELECT COUNT(*) FROM likes) AS likes,
		  (SELECT COUNT(*) FROM plays) AS plays,
		  (SELECT COUNT(*) FROM tags)  AS tags,
		  (SELECT COUNT(*) FROM jobs)  AS jobs`) as Array<Record<string, number>>;
	console.log('after:', counts);
	await sql.end();
}

await main();
