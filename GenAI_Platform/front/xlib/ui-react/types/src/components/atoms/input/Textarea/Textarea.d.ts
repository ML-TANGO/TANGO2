/// <reference types="react" />
import { Properties as CSSProperties } from 'csstype';
import i18n from 'react-i18next';
declare type Props = {
    value?: string;
    name?: string;
    status?: string;
    size?: string;
    isDisabled?: boolean;
    isReadOnly?: boolean;
    placeholder?: string;
    customStyle?: CSSProperties;
    testId?: string;
    theme?: ThemeType;
    options?: {
        [key: string]: string;
    };
    maxLength?: number;
    isShowMaxLength?: boolean;
    autoFocus?: boolean;
    readonly onChange?: (e: React.ChangeEvent<HTMLTextAreaElement>) => void;
    readonly t?: i18n.TFunction<'translation'>;
};
declare function Textarea({ status, size, value, name, placeholder, isReadOnly, isDisabled, customStyle, testId, theme, options, maxLength, isShowMaxLength, autoFocus, onChange, t, ...rest }: Props): JSX.Element;
declare namespace Textarea {
    var defaultProps: {
        value: undefined;
        name: undefined;
        isDisabled: boolean;
        isReadOnly: boolean;
        placeholder: string;
        status: string;
        size: string;
        customStyle: undefined;
        testId: undefined;
        theme: "jp-primary";
        maxLength: number;
        isShowMaxLength: boolean;
        options: undefined;
        autoFocus: boolean;
        onChange: undefined;
        t: undefined;
    };
}
export default Textarea;
