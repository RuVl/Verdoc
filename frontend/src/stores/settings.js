import {defineStore} from 'pinia';
import {DEFAULT_LOCALE, setI18nLanguage, SUPPORT_LOCALES} from '@/i18n/index.js';

function getUserLocale() {
	let user_locale = navigator.language.split('-')[0];
	return SUPPORT_LOCALES.includes(user_locale) ? user_locale : DEFAULT_LOCALE;
}

export const useSettingsStore = defineStore('settings', {
	state: () => ({
		currentLanguage: getUserLocale(),
		currentCurrency: 'USD'
	}),
	actions: {
		async setLanguage(language) {
			this.currentLanguage = language;
			await setI18nLanguage(language);
		},
		setCurrency(currency) {
			this.currentCurrency = currency;
		}
	},
	persist: true
});
