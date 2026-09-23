import type { SongRow } from '$lib/db/library.js';

/**
 * The player's own state: what plays, in what order, how loud, how far in.
 * One audio element lives in the player bar; this is what it reads.
 */
export type Repeat = 'off' | 'all' | 'one';

type State = {
	current: SongRow | null;
	queue: SongRow[];
	index: number;
	playing: boolean;
	shuffle: boolean;
	repeat: Repeat;
	at: number;
	duration: number;
	volume: number;
	muted: boolean;
	drawer: boolean;
	/** what the page is showing, so the dock's play button has a first song */
	page_items: SongRow[];
	counted: Set<string>;
};

const state = $state<State>({
	current: null,
	queue: [],
	index: -1,
	playing: false,
	shuffle: false,
	repeat: 'off',
	at: 0,
	duration: 0,
	volume: 1,
	muted: false,
	drawer: false,
	page_items: [],
	counted: new Set()
});

/** minute and second, the shape every timestamp takes */
function mmss(seconds: number): string {
	const s = Math.max(0, Math.floor(seconds || 0));
	return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

export const player = {
	get current() {
		return state.current;
	},
	get queue() {
		return state.queue;
	},
	get playing() {
		return state.playing;
	},
	get shuffle() {
		return state.shuffle;
	},
	get repeat() {
		return state.repeat;
	},
	get at() {
		return state.at;
	},
	get duration() {
		return state.duration;
	},
	get volume() {
		return state.volume;
	},
	get muted() {
		return state.muted;
	},
	get drawer() {
		return state.drawer;
	},
	get progress() {
		return state.duration > 0 ? state.at / state.duration : 0;
	},

	mmss,

	/** the page tells the player what is on it */
	set_page(items: SongRow[]) {
		state.page_items = items;
	},

	/** start a song, with the list it came from as the queue */
	load(list: SongRow[], start: SongRow) {
		state.queue = [...list];
		state.index = state.queue.findIndex((s) => s.id === start.id);
		state.current = start;
		state.at = 0;
		state.duration = start.seconds || 0;
		state.playing = true;
	},

	set_time(at: number, duration: number) {
		state.at = at;
		if (Number.isFinite(duration) && duration > 0) state.duration = duration;
	},

	set_playing(playing: boolean) {
		state.playing = playing;
	},

	toggle_shuffle() {
		state.shuffle = !state.shuffle;
	},

	cycle_repeat(): Repeat {
		state.repeat = state.repeat === 'off' ? 'all' : state.repeat === 'all' ? 'one' : 'off';
		return state.repeat;
	},

	set_volume(volume: number) {
		state.volume = Math.max(0, Math.min(1, volume));
		state.muted = state.volume === 0;
	},

	toggle_mute() {
		state.muted = !state.muted;
	},

	/** play something, even with nothing chosen yet: the page's first song */
	play_anything(): boolean {
		if (state.current) {
			state.playing = !state.playing;
			return true;
		}
		const first = state.page_items[0];
		if (!first) return false;
		this.load(state.page_items, first);
		return true;
	},

	open_drawer() {
		state.drawer = true;
	},

	close_drawer() {
		state.drawer = false;
	},

	/** the next song, under the current shuffle and repeat rules */
	next(): SongRow | null {
		if (!state.queue.length) return null;
		if (state.repeat === 'one') return state.current;
		let i: number;
		if (state.shuffle) {
			i = state.queue.length === 1 ? 0 : Math.floor(Math.random() * state.queue.length);
		} else {
			i = state.index + 1;
			if (i >= state.queue.length) {
				if (state.repeat !== 'all') return null;
				i = 0;
			}
		}
		return this.jump(i);
	},

	previous(): SongRow | null {
		if (state.at > 3 || !state.queue.length) return null;
		const i = state.shuffle ? Math.floor(Math.random() * state.queue.length) : state.index - 1;
		return this.jump(i < 0 ? state.queue.length - 1 : i);
	},

	jump(i: number): SongRow | null {
		const song = state.queue[i];
		if (!song) return null;
		state.index = i;
		state.current = song;
		state.at = 0;
		state.duration = song.seconds || 0;
		state.playing = true;
		return song;
	},

	/** one play per song per browser session; the server counts what it is sent */
	async count_play(id: string): Promise<void> {
		if (state.counted.has(id)) return;
		state.counted.add(id);
		await fetch(`/api/play/${id}`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ seconds: 0 })
		}).catch(() => undefined);
	}
};

export type { SongRow };

/** the heart: it knows which verb the current state needs */
export async function toggle_like(id: string, liked: boolean): Promise<boolean> {
	const r = await fetch(`/api/like/${id}`, { method: liked ? 'DELETE' : 'POST' }).catch(() => null);
	if (!r?.ok) return liked;
	const body = (await r.json()) as { liked: boolean };
	return body.liked;
}
