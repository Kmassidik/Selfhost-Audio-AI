/**
 * Two themes, one switch. The choice is the visitor's and it survives a
 * reload; the page never flashes the wrong one because the layout applies it
 * before paint.
 */
type Theme = 'light' | 'dark';

const KEY = 'dalang.theme';

let current = $state<Theme>('light');

function apply(theme: Theme) {
	current = theme;
	if (typeof document !== 'undefined') document.documentElement.dataset.theme = theme;
	if (typeof localStorage !== 'undefined') localStorage.setItem(KEY, theme);
}

export const theme = {
	get current() {
		return current;
	},

	/** read the stored choice, or ask the operating system */
	init() {
		if (typeof localStorage === 'undefined') return;
		const stored = localStorage.getItem(KEY) as Theme | null;
		const prefersDark =
			typeof matchMedia !== 'undefined' && matchMedia('(prefers-color-scheme: dark)').matches;
		apply(stored ?? (prefersDark ? 'dark' : 'light'));
	},

	toggle() {
		apply(current === 'light' ? 'dark' : 'light');
	}
};
