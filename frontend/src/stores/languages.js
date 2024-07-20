import {defineStore} from 'pinia';
import {useSettingsStore} from "@/stores/settings.js";

export const useLanguagesStore = defineStore('languages', {
	state: () => {
		const settingsStore = useSettingsStore();
		const languages = [
			{code: 'en', flag: 'gb', name: 'English'},
			{code: 'ru', flag: 'ru', name: 'Русский'},
		];
		const currentLanguage = languages.find(v => v.code === settingsStore.currentLanguage);
		return {
			languages,
			currentLanguage
		};
	},
	actions: {
		async setLanguage(language) {
			this.currentLanguage = language;
			const settingsStore = useSettingsStore();
			await settingsStore.setLanguage(language.code);
		}
	}
});
