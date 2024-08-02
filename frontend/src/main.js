import './assets/main.css'

import {createApp} from 'vue'
import App from '@/App.vue'
import router from "@/router/index.js";
import pinia from "@/stores/index.js";
import {setupI18n} from '@/i18n/index.js';
import {useSettingsStore} from "@/stores/settings.js";

const app = createApp(App);

app.use(router);
app.use(pinia);

const settingsStore = useSettingsStore();
const i18n = await setupI18n({locale: settingsStore.currentLanguage});
app.use(i18n);

app.mount('#app');
