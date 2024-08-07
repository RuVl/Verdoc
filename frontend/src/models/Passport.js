import TranslatableModel from './TranslatableModel';
import {useCurrenciesStore} from "@/stores/currencies.js";
import {assign} from "lodash";

export default class Passport extends TranslatableModel {
	constructor(data) {
		super(data);

		this.id = data.id;
		this.code = data.code; // Country code
		this.price = data.price;
		this._quantity = data._quantity;
		this.max_quantity = data.max_quantity;
	}

	static fromApi(passport, country) {
		const data = {
			id: passport.id,
			code: country.code,
			price: {
				amount: passport.price,
				currency: passport.price_currency
			},
			_quantity: 1, // default quantity to buy
			max_quantity: passport.quantity,
		};

		return new Passport(assign(passport, data));
	}

	get amount() {
		const currenciesStore = useCurrenciesStore();
		return currenciesStore.convert(this.price.amount, this.price.currency);
	}

	formattedPrice(use_quantity = false) {
		const currenciesStore = useCurrenciesStore();
		const price = use_quantity ? this.amount * this._quantity : this.amount;
		return `${price.toFixed(2)} ${currenciesStore.currentCurrency.sign}`;
	}

	getTranslationFields() {
		return ['name'];
	}

	get quantity() {
		return this._quantity;
	}

	set quantity(value) {
		if (value < 1) {
			this._quantity = 1;
			return;
		}
		if (value > this.max_quantity) {
			this._quantity = this.max_quantity;
			return;
		}
		this._quantity = value;
	}
}
