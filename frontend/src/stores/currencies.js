import {defineStore} from 'pinia';
import {useSettingsStore} from "@/stores/settings.js";
import apiClient from "@/api/index.js";

export const useCurrenciesStore = defineStore('currencies', {
	state: () => {
		const currencies = [
			{sign: '$', code: 'USD', name: 'United States dollar'},
			{sign: '₽', code: 'RUB', name: 'Russian ruble'},
		];

		const settingsStore = useSettingsStore();
		const currentCurrency = currencies.find(v => v.code === settingsStore.currentCurrency);

		return {
			currencies,
			currentCurrency,
			exchangeRates: {}
		};
	},
	actions: {
		setCurrency(currency) {
			this.currentCurrency = currency;
			const settingsStore = useSettingsStore();
			settingsStore.setCurrency(currency.code);
		},
		async updateExchangeRates() {
			try {
				const response = await apiClient.get('/exchange-rates/');
				this.exchangeRates = response.data;
			} catch (error) {
				console.error('Failed to fetch exchange rates:', error);
			}
		},
		convert(amount, fromCurrency, toCurrency = null) {
			toCurrency ||= this.currentCurrency.code;
			if (fromCurrency === toCurrency)
				return amount;

			const rate = this.exchangeRates[toCurrency] / this.exchangeRates[fromCurrency];
			return amount * rate;
		}
	}
});
