<script lang="ts">
	import { player, toggle_like } from '$lib/domain/player.svelte.js';

	/**
	 * The docked player. It owns the one audio element on the page: the
	 * element never unmounts, the source swaps with the current song, and the
	 * element's own events are the only source of truth for the clock.
	 */
	let audio: HTMLAudioElement | null = $state(null);
	let liked = $state(false);
	let toast = $state('');

	$effect(() => {
		const song = player.current;
		if (!audio || !song) return;
		const src = `/media/mp3/${song.id}.mp3`;
		if (audio.getAttribute('src') !== src) {
			audio.setAttribute('src', src);
			void audio.play().catch(() => player.set_playing(false));
		}
	});

	$effect(() => {
		if (!audio) return;
		if (player.playing) void audio.play().catch(() => player.set_playing(false));
		else audio.pause();
	});

	$effect(() => {
		if (!audio) return;
		audio.volume = player.volume;
		audio.muted = player.muted;
	});

	$effect(() => {
		liked = Boolean(player.current?.liked);
	});

	function paint() {
		if (audio) player.set_time(audio.currentTime, audio.duration);
	}

	function seek(event: MouseEvent & { currentTarget: HTMLDivElement }) {
		if (!audio || !Number.isFinite(audio.duration)) return;
		const box = event.currentTarget.getBoundingClientRect();
		audio.currentTime = Math.min(1, Math.max(0, (event.clientX - box.left) / box.width)) * audio.duration;
		paint();
	}

	function volume(event: MouseEvent & { currentTarget: HTMLDivElement }) {
		const box = event.currentTarget.getBoundingClientRect();
		player.set_volume(Math.min(1, Math.max(0, (event.clientX - box.left) / box.width)));
	}

	function ended() {
		if (!player.next() && player.repeat === 'off') player.set_playing(false);
	}

	function previous() {
		if (!player.previous() && audio) audio.currentTime = 0;
	}

	async function heart() {
		if (!player.current) return;
		liked = await toggle_like(player.current.id, liked);
	}

	function say(message: string) {
		toast = message;
		setTimeout(() => (toast = ''), 2600);
	}
</script>

{#if toast}
	<div
		class="fixed bottom-[106px] left-1/2 -translate-x-1/2 z-[60] glass-panel px-4 py-2 rounded-full text-xs font-semibold"
	>{toast}</div>
{/if}

<footer
	class="shrink-0 w-full z-50 h-[90px] glass-panel no-edge px-4 flex items-center justify-between"
>
	<div class="flex items-center gap-3 md:gap-4 w-1/4 min-w-0 sm:min-w-[180px]">
		<div class="w-14 h-14 rounded-md bg-glasshover overflow-hidden grid place-items-center shrink-0">
			{#if player.current}
				<img
					src="/media/covers/{player.current.id}.png?v={player.current.cover_v}"
					alt=""
					class="w-full h-full object-cover"
				/>
			{:else}
				<i class="ph ph-music-note text-muted"></i>
			{/if}
		</div>
		<div class="flex flex-col truncate">
			<button class="text-sm font-bold hover:underline truncate text-left" onclick={() => player.open_drawer()}>
				{player.current?.title ?? 'Nothing playing'}
			</button>
			<span class="text-[11px] text-muted truncate">
				{player.current ? (player.current.tags[0] ?? player.current.model) : 'Pick a song to start'}
			</span>
		</div>
		{#if player.current}
			<button
				class="text-muted hover:text-accent ml-2 shrink-0"
				title={liked ? 'Remove from liked' : 'Like'}
				aria-pressed={liked}
				onclick={heart}
			><i class="{liked ? 'ph-fill' : 'ph'} ph-heart text-lg" style={liked ? 'color:#fa243c' : ''}></i></button>
		{/if}
	</div>

	<div class="flex-1 min-w-0 max-w-2xl flex flex-col items-center justify-center px-2 md:px-4 gap-2">
		<div class="flex items-center gap-4 md:gap-6">
			<button
				class="hover:text-ink transition-colors"
				style={player.shuffle ? 'color:var(--accent)' : ''}
				title="Shuffle"
				onclick={() => player.toggle_shuffle()}
			><i class="ph ph-shuffle text-lg"></i></button>
			<button class="text-muted hover:text-ink transition-colors" title="Previous" onclick={previous}>
				<i class="ph-fill ph-skip-back text-xl"></i>
			</button>
			<button
				class="w-9 h-9 rounded-full bg-ink text-bg flex items-center justify-center hover:scale-105 active:scale-95 transition-transform shadow-md"
				title={player.playing ? 'Pause' : 'Play'}
				onclick={() => {
					if (!player.play_anything()) say('Nothing to play yet — make a song first');
				}}
			>
				<i class="ph-fill {player.playing ? 'ph-pause' : 'ph-play'} text-lg {player.playing ? '' : 'ml-0.5'}"></i>
			</button>
			<button class="text-muted hover:text-ink transition-colors" title="Next" onclick={() => player.next()}>
				<i class="ph-fill ph-skip-forward text-xl"></i>
			</button>
			<button
				class="hover:text-ink transition-colors"
				style={player.repeat === 'off' ? '' : 'color:var(--accent)'}
				title="Repeat: {player.repeat}"
				onclick={() => player.cycle_repeat()}
			><i class="ph ph-repeat text-lg"></i></button>
		</div>

		<div class="flex items-center gap-2 md:gap-3 w-full text-[11px] text-muted font-medium">
			<span class="w-8 text-right tabular-nums">{player.mmss(player.at)}</span>
			<div
				class="flex-1 h-1.5 bg-line rounded-full overflow-hidden cursor-pointer flex items-center relative"
				role="slider"
				tabindex="0"
				aria-label="Seek"
				aria-valuemin={0}
				aria-valuemax={100}
				aria-valuenow={Math.round(player.progress * 100)}
				onclick={seek}
			>
				<div class="h-full bg-ink hover:bg-accent transition-colors" style="width:{player.progress * 100}%"></div>
				<div
					class="absolute w-3 h-3 bg-white rounded-full shadow -translate-x-1/2"
					style="left:{player.progress * 100}%"
				></div>
			</div>
			<span class="w-8 tabular-nums">{player.mmss(player.duration)}</span>
		</div>
	</div>

	<div class="hidden md:flex items-center justify-end gap-4 w-1/4 min-w-[150px] text-muted">
		<button
			class="flex items-center gap-2 px-4 py-1.5 rounded-full border border-line hover:bg-glasshover text-xs font-semibold text-ink transition-colors"
			onclick={() => player.open_drawer()}
		><i class="ph ph-list text-sm"></i> Details</button>
		<button
			class="hover:text-ink transition-colors"
			title={player.muted ? 'Unmute' : 'Mute'}
			onclick={() => player.toggle_mute()}
		><i class="ph-fill {player.muted || player.volume === 0 ? 'ph-speaker-x' : 'ph-speaker-high'} text-lg"></i></button>
		<div
			class="w-24 h-1.5 bg-line rounded-full overflow-hidden cursor-pointer flex items-center relative"
			role="slider"
			tabindex="0"
			aria-label="Volume"
			onclick={volume}
		>
			<div
				class="h-full bg-ink hover:bg-accent transition-colors"
				style="width:{(player.muted ? 0 : player.volume) * 100}%"
			></div>
		</div>
	</div>

	<audio
		bind:this={audio}
		preload="metadata"
		onplay={() => {
			player.set_playing(true);
			if (player.current) void player.count_play(player.current.id);
		}}
		onpause={() => player.set_playing(false)}
		ontimeupdate={paint}
		onloadedmetadata={paint}
		onended={ended}
		onerror={() => player.current && say('This song’s audio is missing — its file may have been cleaned')}
	></audio>
</footer>
