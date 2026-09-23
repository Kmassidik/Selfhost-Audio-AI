<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { page } from '$app/state';
	import { player, toggle_like, type SongRow } from '$lib/domain/player.svelte.js';
	import { playlist_dialog } from '$lib/domain/playlist-dialog.svelte.js';

	/**
	 * One song as a sleeve. Filing and liking sit together at the top-left; the
	 * play button waits in the middle of the artwork until the card is hovered
	 * or focused. Under the title: what it is, and who made it with what.
	 */
	let { song, list, wide = false, playlist_id = 0 } = $props<{
		song: SongRow;
		list: SongRow[];
		wide?: boolean;
		playlist_id?: number;
	}>();

	let liked = $state(song.liked);
	$effect(() => {
		liked = song.liked;
	});

	const model_name = $derived(
		(page.data as { model_names?: Record<string, string> }).model_names?.[song.model] ?? song.model
	);
	const maker = $derived(song.creator_id && song.creator_id !== 'migrated' ? song.creator_id : '');

	async function heart() {
		liked = await toggle_like(song.id, liked);
	}

	async function leave_playlist() {
		await fetch(`/api/playlists/${playlist_id}/songs/${song.id}`, { method: 'DELETE' });
		await invalidateAll();
	}

	const button =
		'grid h-8 w-8 place-items-center rounded-full bg-black/45 text-white backdrop-blur-sm opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 [@media(hover:none)]:opacity-100';
</script>

<div class="group cursor-pointer {wide ? 'shrink-0 w-[280px] md:w-[320px]' : ''}" data-song={song.id}>
	<div
		class="{wide ? 'aspect-square rounded-2xl' : 'aspect-square rounded-xl'} overflow-hidden mb-2 relative shadow-md"
		role="button"
		tabindex="0"
		aria-label="Play {song.title}"
		onclick={() => player.load(list, song)}
		onkeydown={(e) => (e.key === 'Enter' || e.key === ' ') && player.load(list, song)}
	>
		<img
			src="/media/covers/{song.id}.png?v={song.cover_v}"
			alt=""
			loading="lazy"
			class="absolute inset-0 w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
		/>

		<!-- the play button, in the middle, only when the card is being used -->
		<div
			class="absolute inset-0 flex items-center justify-center bg-black/35 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100 backdrop-blur-[2px]"
		>
			<span class="grid h-12 w-12 place-items-center rounded-full bg-white text-black shadow-lg">
				<i class="ph-fill ph-play text-lg"></i>
			</span>
		</div>

		<!-- filing and liking, together, top-left -->
		<div class="absolute top-2 left-2 flex gap-1.5">
			{#if playlist_id}
				<button
					class={button}
					title="Remove from this playlist"
					onclick={(e) => {
						e.stopPropagation();
						leave_playlist();
					}}
				><i class="ph ph-minus-circle text-sm"></i></button>
			{:else}
				<button
					class={button}
					title="Add to playlist"
					onclick={(e) => {
						e.stopPropagation();
						playlist_dialog.open(song.id, song.title);
					}}
				><i class="ph ph-list-plus text-sm"></i></button>
			{/if}
			<button
				class={button}
				title={liked ? 'Remove from liked' : 'Like'}
				aria-pressed={liked}
				onclick={(e) => {
					e.stopPropagation();
					heart();
				}}
			><i class="{liked ? 'ph-fill' : 'ph'} ph-heart text-sm" style={liked ? 'color:#fa243c' : ''}></i></button>
		</div>
	</div>

	<h4 class="text-sm font-semibold truncate group-hover:underline">{song.title}</h4>
	<p class="text-xs text-muted truncate">
		{song.tags[0] ?? 'Song'} · {player.mmss(song.seconds)}
	</p>
	<p class="text-[11px] text-muted truncate">
		{maker ? `${maker} · ` : ''}{model_name}
	</p>
</div>
