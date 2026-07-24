import {createRouter, createWebHistory} from 'vue-router';
import {useSettingsStore} from "@/stores/settings.js";
import {SUPPORT_LOCALES} from "@/i18n/index.js";

// parent in meta - for navbar upside the block (PathNav.vue in ViewBlock.vue)
const routes = [
    {
        name: 'main',
        path: '',
        component: () => import("@/views/Home.vue"),
        meta: {name: 'routes.main'}
    },
    {
        name: 'info',
        path: '/info',
        component: () => import("@/views/Info.vue"),
        meta: {parent: 'main', name: 'routes.info'}
    },
    {
        name: 'contacts',
        path: '/contacts',
        component: () => import("@/views/Contacts.vue"),
        meta: {parent: 'main', name: 'routes.contacts'}
    },
    {
        name: 'purchases',
        path: '/purchases',
        component: () => import("@/views/MyPurchases.vue"),
        meta: {parent: 'main', name: 'routes.my_purchases'}
    },
    {
        name: 'cart',
        path: '/cart',
        component: () => import("@/views/Cart.vue"),
        meta: {parent: 'main', name: 'routes.cart'}
    },
    {
        name: 'support',
        path: '/support',
        component: () => import("@/views/Support.vue"),
        meta: {parent: 'main', name: 'routes.support'}
    },
    {
        path: '/:pathMatch(.*)*',
        component: () => import("@/views/PageNotFound.vue")
    }
];

const router = createRouter({
    history: createWebHistory(),
    routes: routes,
});

router.beforeEach(async (to, from, next) => {
    const lang = to.query.lang;
    if (lang && SUPPORT_LOCALES.includes(lang)) {
        const settingsStore = useSettingsStore();
        await settingsStore.setLanguage(lang);
    }
    next();
});

export default router;
