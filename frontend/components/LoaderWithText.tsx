"use client"


import { useState } from "react"
import { Loader } from "./ui/loader"

export function LoaderWithText() {
    const [text, setText] = useState("Loading...")

    // Only include variants that support text
    const variant = "text-shimmer"

    return (
        <div className="flex w-full h-96 items-center justify-center">
            <Loader variant={variant} text={text} />

        </div>
    )
}
