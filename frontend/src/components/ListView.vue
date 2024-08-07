<script setup>
defineProps({
  elements: {
    type: Array
  }
});
</script>

<template>
  <div class="products-list">
    <span v-if="$slots.title" class="title"><slot name="title"/></span>
    <ul v-if="elements">
      <li v-for="(element, index) in elements">
        <slot :element="element" :index="index" />
      </li>
    </ul>
  </div>
</template>

<style scoped lang="scss">
.products-list {
  & > .title {
    margin: 30px 0 15px 0;
    display: flex;
    align-items: center;
    gap: 10px;

    font-size: 24px;
    font-weight: bolder;
  }

  & > ul {
    & > li {
      list-style: none;

      display: flex;
      align-items: center;
      gap: 10px 25px;
      padding: 15px 0;
      border-bottom: 1px solid var(--second-color);

      font-size: 14px;
      font-weight: 600;
      line-height: 24px;
      text-wrap: nowrap;

      &:last-child {
        border-bottom: none;
      }
    }
  }
}

@media screen and (max-width: 1024px) {
  .products-list {
    border-bottom: 1px solid var(--second-color);

    .title {
      justify-content: center;
    }
    
    > ul {
      > li {
        flex-wrap: wrap;
        gap: 10px 20px;
      }
    }
  }
}

@media screen and (max-width: 480px){
.products-list > ul > li {
  gap: 10px 5px;
}
}
</style>