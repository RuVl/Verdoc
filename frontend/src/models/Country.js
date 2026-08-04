import TranslatableModel from './TranslatableModel';
import Product from "@/models/Product.js";
import {assign} from "lodash";

export default class Country extends TranslatableModel {
    constructor(data) {
        super(data);

        this.id = data.id;
        this.code = data.code;
        this.products = data.products;
    }

    static fromApi(country) {
        const data = {
            id: parseInt(country.id),
            code: country.code,
            products: country.products.map(product => Product.fromApi(product, country)),
        };
        return new Country(assign(country, data));
    }

    getTranslationFields() {
        return ['name'];
    }
}
