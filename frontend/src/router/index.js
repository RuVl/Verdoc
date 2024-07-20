import {createRouter, createWebHistory} from 'vue-router';

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
];

const router = createRouter({
	history: createWebHistory(),
	routes,
});

export default router;
