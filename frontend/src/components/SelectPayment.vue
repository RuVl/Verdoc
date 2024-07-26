<script setup>
import CommonButton from "@/components/CommonButton.vue";
import ModalWindow from "@/components/ModalWindow.vue";
import CustomSelect from "@/components/CustomSelect.vue";
import InputWrapper from "@/components/InputWrapper.vue";
import Passport from "@/models/Passport.js";
import {useOrderStore} from "@/stores/order.js";
import {ref} from "vue";

const is_opened = defineModel('is_opened', {default: true});
const user_email = ref();
const payment_method_index = ref(0);

const props = defineProps({
  passport: Passport
});

const orderStore = useOrderStore();

function buy() {
  const payment_method = orderStore.payment_methods[payment_method_index.value];
  if (payment_method.name !== 'plisio') return;

  if (props.passport) orderStore.buyPassport(props.passport, user_email.value);
  else orderStore.makeOrder(user_email.value);

  is_opened.value = false;
}
</script>

<template>
  <ModalWindow v-model:is_opened="is_opened">
    <template #title>{{ $t('cart_view.modal_window.title') }}</template>
    <template #default>
      <form class="payment-form" @submit.prevent="buy">
        {{ $t('cart_view.modal_window.email.ask') }}
        <InputWrapper><input name="user_email" v-model="user_email" type="email" :placeholder="$t('cart_view.modal_window.email.placeholder')"></InputWrapper>
        {{ $t('cart_view.modal_window.choose_method') }}
        <CustomSelect v-model:selected="payment_method_index" :elements="orderStore.payment_methods" class="payment-method">
          <template #default="{element: method}">
            <img class="option-icon" :src="method.icon"/>
            <span class="option-text">{{ method.name }}</span>
          </template>
          <template #hidden-input="{element: method}">
            <input type="hidden" name="payment-method" :value="method.name">
          </template>
        </CustomSelect>
        <CommonButton type="submit" class="submit-btn">{{ $t('buttons.payment_method') }}</CommonButton>
      </form>
    </template>
  </ModalWindow>
</template>

<style scoped lang="scss">
.payment-form {
  display: flex;
  gap: 15px;
  flex-direction: column;
  align-items: center;
  font-size: 14px;
  font-weight: 500;
  margin: 0 20px;

  .payment-method {
    .dropdown-toggle {
      padding: 0 10px;
    }

    .option-text {
      text-transform: capitalize;
      font-size: 14px;
      font-weight: 500;
      line-height: 24px;
      margin-left: 10px;
    }

    .option-icon {
      height: 30px;
    }
  }

  .submit-btn {
    margin-top: 30px;
    font-weight: normal;
  }
}
</style>