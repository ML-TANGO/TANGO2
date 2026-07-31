import { Story } from '@storybook/react';
import PageTemplate, { PageTemplateArgs } from './PageTemplate';
declare const _default: {
    title: string;
    component: typeof PageTemplate;
    argTypes: {
        theme: {
            options: string[];
            control: {
                type: string;
            };
        };
    };
    decorators: ((storyFn: any) => JSX.Element)[];
};
export default _default;
export declare const PageTemplateSample: Story<PageTemplateArgs>;
