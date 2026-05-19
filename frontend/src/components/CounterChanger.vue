<script setup>
import CounterShow from "@/components/CounterShow.vue";

const item = defineModel('item', {required: true});
const props = defineProps({
  counter_name: {
    type: String,
    default: 'count'
  }
});

const max_count_name = `max_${props.counter_name}`;
</script>

<template>
  <div class="counter-changer">
    <button :disabled="item[counter_name] <= 1" type="button" @click="item[counter_name]--">–</button>
    <CounterShow>{{ item[counter_name] }} {{ $t('products.count') }}</CounterShow>
    <button :disabled="item[counter_name] >= item[max_count_name]" type="button" @click="item[counter_name]++">+
    </button>
  </div>
</template>

<style lang="scss" scoped>
.counter-changer {
  > button {
    user-select: none;
    background: none;
    border: 0;
    font-weight: 600;
    font-size: 24px;
    margin: 10px;
    cursor: pointer;

    &:hover, &:disabled {
      opacity: .7;
    }
  }


}
</style>