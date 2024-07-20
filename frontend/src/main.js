import './assets/main.css'

import {createApp} from 'vue'
import App from '@/App.vue'
import router from "@/router/index.js";
import pinia from "@/stores/index.js";
import {setupI18n} from '@/i18n/index.js';
import {useSettingsStore} from "@/stores/settings.js";
import {useCurrenciesStore} from "@/stores/currencies.js";

const app = createApp(App);

app.use(router);
app.use(pinia);

const settingsStore = useSettingsStore();
const i18n = await setupI18n({locale: settingsStore.currentLanguage});
app.use(i18n);

const currencyStore = useCurrenciesStore();
await currencyStore.updateExchangeRates();

app.mount('#app');

setInterval(async () => {
	await currencyStore.updateExchangeRates();
}, 3600_000); // Update currency rate from server every hour
