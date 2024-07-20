import {assign, capitalize, isArray, isEmpty, isObject} from 'lodash';
import { getI18n } from '@/i18n/index.js';

export default class TranslatableModel {
  constructor(data) {
    const translationFields = this.getTranslationFields();
    for (const field of translationFields)
      this.defineProperty(field);

    assign(this, data); // Присваиваем оставшиеся поля
  }

  defineProperty(fieldName) {
    Object.defineProperty(this, fieldName, {
      get() {
        const i18n = getI18n();
        for (const language of this.getUserLanguages(i18n)) {
          const transFieldName = `${fieldName}_${language.toLowerCase()}`;
          const value = this[transFieldName];

          if (!isEmpty(value))
            return value;
        }
        return undefined;
      },
      set(data) {
        const languages = this.getLanguages();
        for (const language of languages) {
          const transFieldName = `${fieldName}_${language.toLowerCase()}`;

          if (!isEmpty(data[transFieldName]))
            this[transFieldName] = data[transFieldName];
        }
      },
    });
  }

  getField(data) {
    return data;
  }

  getTranslationFields() {
    return []; // List of translation fields overrides by child
  }

  getLanguages() {
    const i18n = getI18n();
    const languages = Object.keys(i18n.global.messages);
    return languages.map(capitalize);
  }

  *getUserLanguages(i18n) {
    yield capitalize(i18n.global.locale.value);

    const fallbackLanguages = this.getFallbackLanguages(i18n);
    for (const language of fallbackLanguages)
      yield language;
  }

  getFallbackLanguages(i18n) {
    const userLocale = capitalize(i18n.global.locale.value);
    const fallbackConfig = i18n.global.fallbackLocale.value;

    const locales = isArray(fallbackConfig) ? fallbackConfig :
      isObject(fallbackConfig) ? Object.keys(fallbackConfig) : [fallbackConfig];

    return locales.filter(lang => lang !== userLocale).map(capitalize);
  }
}
