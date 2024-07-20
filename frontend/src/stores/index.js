import {createPinia} from 'pinia';
import piniaPluginPersistedState from 'pinia-plugin-persistedstate'

export const pinia = createPinia().use(piniaPluginPersistedState);

export default pinia;
