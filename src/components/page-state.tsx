import { AlertCircle, LoaderCircle } from "lucide-react";
export function PageLoading({label="Loading your workspace"}:{label?:string}){return <div className="page-state" role="status"><LoaderCircle className="spin"/><p>{label}…</p></div>}
export function PageError({message,retry}:{message:string;retry:()=>void}){return <div className="page-state page-state--error"><AlertCircle/><h2>We hit a snag</h2><p>{message}</p><button className="button button--dark" onClick={retry}>Try again</button></div>}
