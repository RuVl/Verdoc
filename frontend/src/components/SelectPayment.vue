<script setup>
import {reactive} from "vue";
import Product from "@/models/Product.js";
import {useOrderStore} from "@/stores/order.js";
import ModalWindow from "@/components/ModalWindow.vue";
import PrettyInput from "@/components/PrettyInput.vue";
import CommonButton from "@/components/CommonButton.vue";
import CustomSelect from "@/components/CustomSelect.vue";

const is_opened = defineModel('is_opened', {default: true});

const payment_form = reactive({
  email: '',
  method: 0
})

const props = defineProps({
  product: Product
});

const orderStore = useOrderStore();

function buy() {
  const payment_method = orderStore.payment_methods[payment_form.method];
  if (payment_method.name !== 'plisio') return;

  if (props.product) orderStore.buyProduct(props.product, payment_form.email);
  else orderStore.makeOrder(payment_form.email);

  is_opened.value = false;
}
</script>

<template>
  <ModalWindow v-model:is_opened="is_opened">
    <template #title>{{ $t('cart_view.modal_window.title') }}</template>
    <template #default>
      <form class="payment-form" @submit.prevent="buy">
        {{ $t('cart_view.modal_window.email.ask') }}
        <pretty-input v-model="payment_form.email" :placeholder="$t('cart_view.modal_window.email.placeholder')"
                      name="user_email" type="email"/>
        {{ $t('cart_view.modal_window.choose_method') }}
        <CustomSelect v-model:selected="payment_form.method" :elements="orderStore.payment_methods"
                      class="payment-method">
          <template #default="{element: method}">
            <img :src="method.icon" class="option-icon"/>
            <span class="option-text">{{ method.name }}</span>
          </template>
          <template #hidden-input="{element: method}">
            <input :value="method.name" name="payment-method" type="hidden">
          </template>
        </CustomSelect>
        <CommonButton class="submit-btn" type="submit">{{ $t('buttons.payment_method') }}</CommonButton>
      </form>
    </template>
  </ModalWindow>
</template>

<style lang="scss" scoped>
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