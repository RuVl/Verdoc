import TranslatableModel from './TranslatableModel';
import {useCurrenciesStore} from "@/stores/currencies.js";
import {assign} from "lodash";

export default class Passport extends TranslatableModel {
	constructor(data) {
		super(data);

		this.id = data.id;
		this.code = data.code; // Country code
		this.price = data.price;
		this.quantity = data.quantity;
		this.max_quantity = data.max_quantity;
	}

	static fromApi(passport, country) {
		const data = {
			id: passport.id,
			code: country.code,
			price: passport.price,
			quantity: 1, // default quantity to buy
			max_quantity: passport.quantity,
		};

		return new Passport(assign(passport, data));
	}

	get amount() {
		const currenciesStore = useCurrenciesStore();
		return currenciesStore.convert(this.price.amount, this.price.currency);
	}

	get formattedPrice() {
		const currenciesStore = useCurrenciesStore();
		return `${this.amount.toFixed(2)} ${currenciesStore.currentCurrency.sign}`;
	}

	getTranslationFields() {
		return ['name'];
	}
}
