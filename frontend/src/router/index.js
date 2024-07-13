import {createRouter, createWebHistory} from 'vue-router';

const routes = [
	{
		name: 'main',
		path: '',
		component: () => import("@/views/Home.vue"),
		meta: {title: 'Главная'}
	},
	{
		name: 'info',
		path: '/info',
		component: () => import("@/views/Info.vue"),
		meta: {parent: 'main', title: 'Информация'}
	},
	{
		name: 'contacts',
		path: '/contacts',
		component: () => import("@/views/Contacts.vue"),
		meta: {parent: 'main', title: 'Контакты'}
	},
	{
		name: 'purchases',
		path: '/purchases',
		component: () => import("@/views/MyPurchases.vue"),
		meta: {parent: 'main', title: 'Мои покупки'}
	},
	{
		name: 'cart',
		path: '/cart',
		component: () => import("@/views/Cart.vue"),
		meta: {parent: 'main', title: 'Корзина'}
	},
	{
		name: 'support',
		path: '/support',
		component: () => import("@/views/Support.vue"),
		meta: {parent: 'main', title: 'Поддержка'}
	},
];

const router = createRouter({
	history: createWebHistory(),
	routes,
});

export default router;
