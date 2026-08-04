import TranslatableModel from './TranslatableModel';
import {useCurrenciesStore} from "@/stores/currencies.js";
import {assign} from "lodash";

export default class Product extends TranslatableModel {
    constructor(data) {
        super(data);

        this.id = data.id;
        this.code = data.code; // Country code
        this.price = data.price;
        this._quantity = data._quantity;
        this.max_quantity = data.max_quantity;
    }

    get amount() {
        const currenciesStore = useCurrenciesStore();
        return currenciesStore.convert(this.price.amount, this.price.currency);
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

    static fromApi(product, country) {
        const data = {
            id: parseInt(product.id),
            code: country.code,
            price: {
                amount: parseFloat(product.price),
                currency: product.price_currency
            },
            _quantity: 1, // default quantity to buy
            max_quantity: parseInt(product.available),
        };

        return new Product(assign(product, data));
    }

    formattedPrice(use_quantity = false) {
        const currenciesStore = useCurrenciesStore();
        const price = use_quantity ? this.amount * this._quantity : this.amount;
        return `${price.toFixed(2)} ${currenciesStore.currentCurrency.sign}`;
    }

    getTranslationFields() {
        return ['name'];
    }
}
