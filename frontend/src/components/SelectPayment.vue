<script setup>
import CommonButton from "@/components/CommonButton.vue";
import ModalWindow from "@/components/ModalWindow.vue";
import CustomSelect from "@/components/CustomSelect.vue";
import InputWrapper from "@/components/InputWrapper.vue";
import Passport from "@/models/Passport.js";
import {useOrderStore} from "@/stores/order.js";

const is_opened = defineModel('is_opened', {default: true});

const props = defineProps({
  passport: Passport
});

const orderStore = useOrderStore();

function buy() {
  if (props.passport) orderStore.buyPassport(props.passport);
  else orderStore.makeOrder();

  is_opened.value = false;
}
</script>

<template>
  <ModalWindow v-model:is_opened="is_opened">
    <template #title>{{ $t('cart_view.modal_window.title') }}</template>
    <template #default>
      <form class="payment-form" method="post">
        {{ $t('cart_view.modal_window.email.ask') }}
        <InputWrapper><input type="email" :placeholder="$t('cart_view.modal_window.email.placeholder')"></InputWrapper>
        {{ $t('cart_view.modal_window.choose_method') }}
        <CustomSelect :elements="orderStore.payment_methods" class="payment-method">
          <template #default="{element: method}">
            <img class="option-icon" :src="method.icon"/>
            <span class="option-text">{{ method.name }}</span>
          </template>
          <template #hidden-input="{element: method}">
            <input type="hidden" name="payment-method" :value="method.name">
          </template>
        </CustomSelect>
        <CommonButton @click="buy()" class="submit-btn">{{ $t('buttons.payment_method') }}</CommonButton>
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