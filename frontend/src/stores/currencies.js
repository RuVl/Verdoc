import {defineStore} from 'pinia';
import {useSettingsStore} from "@/stores/settings.js";
import {fetchExchangeRates} from "@/api/catalog.js";

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
                this.exchangeRates = await fetchExchangeRates();
            } catch (error) {
                // Prices keep the last rates rather than the switch going blank mid-visit.
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

// The first fetch and the hourly refresh live in App.vue: running them here would fire on import,
// before pinia is installed, and leave an interval nothing ever clears.
export const EXCHANGE_RATES_INTERVAL_MS = 3600_000;
