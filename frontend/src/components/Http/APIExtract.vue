<template>
  <n-form :model="formModel">
    <n-dynamic-input
      v-model:value="inputData"
      :on-create="onCreate"
      :on-remove="onRemove"
      #="{ index, value }"
    >
      <tr>
        <td>
          <n-form-item
            ignore-path-change
            :show-label="false"
            :rule="DuplicateNameRule"
            :path="`inputData[${index}].name`"
          >
            <n-input
              v-model:value="value.name"
              type="text"
              placeholder="变量名"
              @update:value="onChange"
            />
          </n-form-item>
        </td>
        <td>
          <n-select
            v-model:value="value.attr"
            :options="RespAttrOptions"
            placeholder="响应属性"
            :consistent-menu-width="false"
            @update:value="onChange"
          />
        </td>
        <td>
          <n-input
            v-model:value="value.expr"
            type="text"
            placeholder="表达式"
            @update:value="onChange"
          />
        </td>
        <td>
          <n-input-number
            v-model:value="value.num"
            min="0"
            placeholder="索引"
            @update:value="onChange"
          />
        </td>
      </tr>
    </n-dynamic-input>
  </n-form>
</template>

<script lang="ts" setup>
  import { ref, computed, Ref, watchEffect } from 'vue';
  import { RespAttrOptions } from './apiSelectOptions';

  interface InputDataItem {
    name: string;
    attr: string;
    expr: string;
    num: number;
  }
  const props = defineProps({
    data: {
      type: Object,
      required: true,
    },
  });

  const emit = defineEmits(['someEvent']);

  // 子组件输入的值
  const inputData: Ref<InputDataItem[]> = ref([onCreate()]);

  //子组件传出的值
  const dictDict = computed(() =>
    inputData.value.reduce((acc, curr) => {
      acc[curr.name] = [curr.attr, curr.expr, curr.num];
      return acc;
    }, {})
  );

  // 判断key重复
  const inputKeys = computed(() =>
    inputData.value.reduce((acc: string[], curr) => {
      acc.push(curr.name);
      return acc;
    }, [])
  );

  // 表单的model属性
  const formModel = ref({
    inputData,
  });

  const DuplicateNameRule = {
    trigger: 'input',
    validator(rule: unknown, value: string) {
      if (inputKeys.value.filter((element) => element === value).length > 1)
        return new Error('变量名重复');
      return true;
    },
  };

  function onCreate() {
    return {
      name: '',
      attr: 'status_code',
      expr: '',
      num: 0,
    };
  }

  function onChange() {
    emit('someEvent', dictDict.value);
    return 1;
  }

  function onRemove() {
    setTimeout(() => onChange(), 20);
  }

  watchEffect(() => {
    // console.log(`props.data`, props.data);
    // console.log(`inputKeys`, inputKeys);

    if (inputKeys.value.length === 1 && inputKeys.value[0] === '' && props.data) {
      inputData.value = [];
      Object.entries(props.data).map(([name, detail]) => {
        let attr = detail[0];
        let expr = detail[1];
        let num = detail[2];

        inputData.value.push({
          name,
          attr,
          expr,
          num,
        });
      });
    } else {
      // console.log('收到父组件数据，但是不更新子组件内容');
    }
  });
</script>
