import { basename, join } from 'node:path';
import type { RequestHandler } from './$types';

/**
 * media — byte-range serving from the data tree (mounted read-only at /data).
 * Covers, MP3s and video are public; the master WAV is the owner's.
 */
const KINDS = {
	mp3: { dir: 'mp3', type: 'audio/mpeg' },
	audio: { dir: 'audio', type: 'audio/wav' },
	covers: { dir: 'covers', type: 'image/png' },
	video: { dir: 'video', type: 'video/mp4' },
	assets: { dir: 'assets', type: 'image/jpeg' }
} as const;
type Kind = keyof typeof KINDS;

/** a stored song file name: digits, dashes and letters, never a path */
const SONG_FILE = /^[0-9][0-9a-z.-]*\.(mp3|wav|png|mp4|jpg)$/;

export const GET: RequestHandler = async ({ params, request }) => {
	const spec = KINDS[params.kind as Kind];
	const name = basename(params.id);
	if (!spec || !SONG_FILE.test(name)) return new Response(null, { status: 404 });

	const file = Bun.file(join(process.env.DATA_DIR ?? '/data', spec.dir, name));
	if (!(await file.exists())) return new Response(null, { status: 404 });

	const headers: Record<string, string> = {
		'accept-ranges': 'bytes',
		'content-type': spec.type,
		'cache-control': 'no-cache'
	};

	const size = file.size;
	const range = request.headers.get('range');
	if (!range?.startsWith('bytes=')) {
		return new Response(file, { headers: { ...headers, 'content-length': String(size) } });
	}

	const [first, last] = range.slice(6).split('-', 2);
	const start = first ? Number(first) : Math.max(0, size - Number(last || 0));
	const end = first && last ? Math.min(Number(last), size - 1) : size - 1;
	if (!Number.isFinite(start) || !Number.isFinite(end) || start > end) {
		return new Response(null, { status: 416, headers: { 'content-range': `bytes */${size}` } });
	}
	return new Response(file.slice(start, end + 1), {
		status: 206,
		headers: {
			...headers,
			'content-range': `bytes ${start}-${end}/${size}`,
			'content-length': String(end - start + 1)
		}
	});
};
