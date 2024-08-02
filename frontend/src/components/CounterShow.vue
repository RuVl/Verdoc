<template>
  <span class="counter"><slot/></span>
</template>

<style scoped lang="scss">
.counter {
  display: inline-block;
  text-align: center;
  min-width: 100px;
  padding: 10px 0;
  background-color: var(--second-color);
  border-radius: 10px;
}

@media screen and (max-width: 480px){
  .counter {
    min-width: 85px;
    padding: 5px 0;
  }
}
</style>