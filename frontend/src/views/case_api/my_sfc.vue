<template>
  <n-form :model="model">
    <n-dynamic-input
      v-model:value="model.dynamicInputValue"
      item-style="margin-bottom: 0;"
      :on-create="onCreate"
      #="{ index, value }"
    >
      <div style="display: flex">
        <!--
            通常，path 的变化会导致 form-item 验证内容或规则的改变，所以 naive-ui 会清理掉
            表项已有的验证信息。但是这个例子是个特殊情况，我们明确的知道，path 的改变不会导致
            form-item 验证内容和规则的变化，所以就 ignore-path-change
          -->
        <n-form-item
          ignore-path-change
          :show-label="false"
          :path="`dynamicInputValue[${index}].name`"
          :rule="dynamicInputRule"
        >
          <n-input
            v-model:value="model.dynamicInputValue[index].name"
            placeholder="Name"
            @keydown.enter.prevent
          />
          <!--
              由于在 input 元素里按回车会导致 form 里面的 button 被点击，所以阻止了默认行为
            -->
        </n-form-item>
        <div style="height: 34px; line-height: 34px; margin: 0 8px"> = </div>
        <n-form-item
          ignore-path-change
          :show-label="false"
          :path="`dynamicInputValue[${index}].value`"
          :rule="dynamicInputRule"
        >
          <n-input
            v-model:value="model.dynamicInputValue[index].value"
            placeholder="Value"
            @keydown.enter.prevent
          />
        </n-form-item>
      </div>
    </n-dynamic-input>
  </n-form>
  <pre>{{ JSON.stringify(model.dynamicInputValue, null, 2) }}</pre>
  {{ data }}
</template>

<script lang="ts" setup>
  import { defineProps, defineEmits, ref, onMounted, watchEffect } from 'vue';
  const props = defineProps(['data']); // 父组件的变量
  const enmit = defineEmits(['update_1231231231']); // 申明事件

  const dynamicInputRule = {
    trigger: 'input',
    validator(rule: unknown, value: string) {
      if (value.length >= 5) return new Error('最多输入四个字符');
      return true;
    },
  };

  const model = ref({
    dynamicInputValue: [{ value: '', name: '' }], // 子组件 变量
  });

  function onCreate() {
    return {
      name: '',
      value: '',
    };
  }

  // 根据父组件的的值，修改子组件变量的值
  // onMounted： 组件被加载时调用
  // watchEffect： 变量被修改时调用

  watchEffect(() => {
    console.log('父组件的变量值', props.data);
    model.value.dynamicInputValue = props.data;
    enmit('update_1231231231', '3333333') // 触发事件  
    enmit('update_1231231231', '2222') // 触发事件  
  });
</script>
