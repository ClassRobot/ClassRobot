const utils = {
    megabyte(size) {
        // console.log(size);
        size /= 1024;
        for (let unit of this.units) {
            if (size >= 1024) size /= 1024;
            else return `${parseInt(size)}${unit}`;
        }
    }
}