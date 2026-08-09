<script setup>
import {reactive, ref} from "vue";
import Product from "@/models/Product.js";
import {useOrderStore} from "@/stores/order.js";
import {errorMessageKey} from "@/api/errors.js";
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
const error = ref(null);
const sending = ref(false);

async function buy() {
  const payment_method = orderStore.payment_methods[payment_form.method];
  if (payment_method.name !== 'plisio') return;

  error.value = null;
  sending.value = true;
  try {
    if (props.product) await orderStore.buyProduct(props.product, payment_form.email);
    else await orderStore.makeOrder(payment_form.email);

    // Closed only on success: on failure the customer stays on the form they can retry from.
    is_opened.value = false;
  } catch (e) {
    // 502 means Plisio refused the invoice. Its own message is English-only and technical, so the
    // customer gets our text and the provider code goes to the console for us.
    error.value = errorMessageKey(e, {502: 'cart_view.modal_window.error.payment_gateway'});
    console.error('Checkout failed:', e.response?.data?.provider_code ?? '', e);
  } finally {
    sending.value = false;
  }
}
</script>

<template>
  <ModalWindow v-model:is_opened="is_opened">
    <template #title>{{ $t('cart_view.modal_window.title') }}</template>
    <template #default>
      <form class="payment-form" @submit.prevent="buy">
        {{ $t('cart_view.modal_window.email.ask') }}
        <pretty-input v-model="payment_form.email" :placeholder="$t('cart_view.modal_window.email.placeholder')"
                      name="email" type="email"/>
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
        <p v-if="error" class="form-error">{{ $t(error) }}</p>
        <CommonButton :disabled="sending" class="submit-btn" type="submit">
          {{ $t('buttons.payment_method') }}
        </CommonButton>
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

  .form-error {
    color: var(--red-color);
    text-align: center;
    margin: 0;
    // align-items: center sizes a flex item to its content, so without this the message runs out
    // of the modal instead of wrapping inside it.
    max-width: 100%;
  }

  .submit-btn {
    margin-top: 30px;
    font-weight: normal;
  }
}
</style>