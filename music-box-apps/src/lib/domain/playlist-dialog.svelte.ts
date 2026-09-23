/**
 * One dialog, opened from anywhere a song appears. It holds only which song
 * is being filed; the lists themselves live in the dialog, fetched on open.
 */
let song_id = $state<string | null>(null);
let song_title = $state('');

export const playlist_dialog = {
	get song_id() {
		return song_id;
	},
	get song_title() {
		return song_title;
	},
	open(id: string, title = '') {
		song_id = id;
		song_title = title;
	},
	close() {
		song_id = null;
		song_title = '';
	}
};
