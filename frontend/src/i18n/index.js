import {nextTick} from 'vue';
import {createI18n} from 'vue-i18n';
import {defaults} from 'lodash';

let i18n;
const loadedLanguages = new Set();

export const DEFAULT_LOCALE = 'en';
export const SUPPORT_LOCALES = ['en', 'ru'];

export async function setupI18n(options = {}) {
	defaults(options, {
		legacy: false,
		locale: DEFAULT_LOCALE,
		fallbackLocale: DEFAULT_LOCALE
	});

	i18n = createI18n(options);
	await setI18nLanguage(options.locale);
	return i18n;
}

export async function setI18nLanguage(language) {
	if (!loadedLanguages.has(language))
		await loadLocaleMessages(language, i18n);

	i18n.global.locale.value = language;
	document.querySelector('html').setAttribute('lang', language);
}

export async function loadLocaleMessages(locale) {
	if (!SUPPORT_LOCALES.includes(locale)) {
		console.warn(`${locale} is not supported`);
		return;
	}

	const messages = await import(`./locales/${locale}.json`);
	i18n.global.setLocaleMessage(locale, messages.default);
	loadedLanguages.add(locale)

	return nextTick();
}

export function getI18n() {
  return i18n;
}
