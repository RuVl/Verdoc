import TranslatableModel from './TranslatableModel';
import Passport from "@/models/Passport.js";
import {assign} from "lodash";

export default class Country extends TranslatableModel {
	constructor(data) {
		super(data);

		this.id = data.id;
		this.code = data.code;
		this.passports = data.passports;
	}

	static fromApi(country) {
		const data = {
			id: country.id,
			code: country.code,
			passports: country.passports.map(passport => Passport.fromApi(passport, country)),
		};
		return new Country(assign(country, data));
	}

	getTranslationFields() {
		return ['name'];
	}
}
