export class Char {
  value;

  constructor(value) {
    if (value.length > 1) {
      throw new Error('not a char');
    }
    this.value = value;
  }

  charCodeAt = (num) => {
    return this.value.charCodeAt(num);
  };

  get getValue() {
    return this.value;
  }
}

export default Char;
