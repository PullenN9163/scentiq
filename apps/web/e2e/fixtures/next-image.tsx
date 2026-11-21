import type {ImgHTMLAttributes} from "react";
// Native image loading lets fixtures exercise the real CatalogImage fallback.
export default function Image({priority, unoptimized, ...props}:ImgHTMLAttributes<HTMLImageElement> & {priority?:boolean;unoptimized?:boolean}) {
  void priority;void unoptimized;
  // A native image is intentional in this test double; Next image optimization is tested by the deployed journey.
  // eslint-disable-next-line @next/next/no-img-element
  return <img {...props} alt={props.alt}/>;
}
